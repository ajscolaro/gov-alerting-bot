import asyncio
import json
import logging
import os
import sys
from typing import Dict, Optional
from datetime import datetime
from pathlib import Path

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.common.alerts.slack import SlackAlertSender
from src.common.alerts.base import AlertConfig
from src.integrations.sky.client import SkyClient, SkyProposal
from src.integrations.sky.alerts import SkyAlertHandler
from src.common.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SkyProposalTracker:
    """Tracks Sky proposals and their status changes with file-based persistence."""
    
    def __init__(self, continuous: bool = False, is_test_mode: Optional[bool] = None):
        # For backward compatibility, derive is_test_mode from continuous if not provided
        self.is_test_mode = not continuous if is_test_mode is None else is_test_mode
        self.state_file = "data/test_proposal_tracking/sky_proposal_state.json" if self.is_test_mode else "data/proposal_tracking/sky_proposal_state.json"
        self.proposals: Dict[str, Dict] = self._load_state()
        logger.info(f"Loaded state from {self.state_file}: {len(self.proposals)} proposals")
    
    def _load_state(self) -> Dict[str, Dict]:
        """Load proposal state from file."""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, "r") as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logger.error(f"Error loading proposal state: {e}")
            return {}
    
    def _save_state(self):
        """Save current proposal state to file."""
        try:
            os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
            with open(self.state_file, "w") as f:
                json.dump(self.proposals, f, indent=2)
            logger.info(f"Saved state to {self.state_file}")
        except Exception as e:
            logger.error(f"Error saving proposal state: {e}")
    
    def get_proposal(self, proposal_id: str, proposal_type: str) -> Optional[Dict]:
        """Get proposal by ID and type."""
        key = f"{proposal_type}:{proposal_id}"
        return self.proposals.get(key)
    
    def update_proposal(self, proposal_id: str, status: str, thread_ts: Optional[str] = None, 
                       alerted: bool = False, proposal_type: str = None, support: Optional[float] = None):
        """Update proposal status."""
        key = f"{proposal_type}:{proposal_id}"
        if key in self.proposals:
            self.proposals[key]["status"] = status
            if thread_ts:
                self.proposals[key]["thread_ts"] = thread_ts
            if alerted:
                self.proposals[key]["alerted"] = True
            if support is not None:
                self.proposals[key]["support"] = support
        else:
            self.proposals[key] = {
                "status": status,
                "thread_ts": thread_ts,
                "alerted": alerted
            }
            if support is not None:
                self.proposals[key]["support"] = support
        self._save_state()
    
    def remove_proposal(self, proposal_id: str, proposal_type: str):
        """Remove proposal by ID and type."""
        key = f"{proposal_type}:{proposal_id}"
        if key in self.proposals:
            del self.proposals[key]
            self._save_state()
    
    def get_tracked_proposals_count(self) -> int:
        """Get the number of currently tracked proposals."""
        return len(self.proposals)

async def load_sky_watchlist():
    """Load the Sky watchlist from file."""
    try:
        with open("data/watchlists/sky_watchlist.json", "r") as f:
            data = json.load(f)
            projects = data.get("projects", [])
            
            # Validate required metadata fields
            for project in projects:
                required_fields = ["poll_url", "executive_url"]
                for field in required_fields:
                    if field not in project["metadata"]:
                        logger.error(f"Missing required field '{field}' in project {project['name']}")
                        return []
            
            return projects
    except Exception as e:
        logger.error(f"Error loading Sky watchlist: {e}")
        return []

async def process_sky_proposal_alert(
    proposal: SkyProposal,
    project: Dict,
    current: Optional[Dict],
    alert_handler: SkyAlertHandler,
    slack_sender: SlackAlertSender,
    tracker: SkyProposalTracker
):
    """Process a Sky proposal alert."""
    previous_status = current["status"] if current else None
    
    if alert_handler.should_alert(proposal, previous_status):
        # Determine alert type based on proposal type and status
        if not previous_status:
            alert_type = "proposal_active"
        elif proposal.type == "poll":
            # For polls, only active and ended states
            alert_type = "proposal_ended" if proposal.status == "ended" else "proposal_active"
        else:  # executive vote
            # For executive votes, handle passed and executed states
            if previous_status == "active" and proposal.status == "passed":
                alert_type = "proposal_update"
            elif previous_status == "passed" and proposal.status == "executed":
                alert_type = "proposal_ended"
            else:
                alert_type = "proposal_update"
        
        logger.info(f"Sending {alert_type} alert for {project['name']} {proposal.type} {proposal.id}")
        
        # Prepare alert data
        alert_data = {
            "project_name": project["name"],
            "proposal": proposal
        }
        
        # Format and send alert
        message = alert_handler.format_alert(alert_type, alert_data)
        
        # Handle thread context
        if alert_type != "proposal_active":
            if current and current.get("thread_ts"):
                message["thread_ts"] = current["thread_ts"]
                logger.info(f"Sending {alert_type} as thread reply with ts: {current['thread_ts']}")
            else:
                message["text"] = f"⚠️ Unable to find original message context. {message['text']}"
                logger.warning(f"No thread context found for {proposal.type} {proposal.id}")
        
        # Get intel_label from project metadata
        intel_label = project.get("intel_label")
        
        # Send the alert with intel_label
        result = await slack_sender.send_alert(alert_handler, message, intel_label=intel_label)
        
        if result["ok"]:
            if alert_type == "proposal_active":
                tracker.update_proposal(
                    proposal.id, 
                    proposal.status, 
                    result["ts"], 
                    True, 
                    proposal_type=proposal.type,
                    support=proposal.support
                )
                logger.info(f"Stored thread timestamp for new proposal: {result['ts']}")
            elif alert_type == "proposal_ended":
                # Remove ended proposals from tracking
                tracker.remove_proposal(proposal.id, proposal_type=proposal.type)
                logger.info(f"Removed ended proposal from tracking: {proposal.id}")
            else:  # proposal_update (only for executive votes)
                tracker.update_proposal(
                    proposal.id, 
                    proposal.status, 
                    current.get("thread_ts"), 
                    True,
                    proposal_type=proposal.type,
                    support=proposal.support
                )
                logger.info(f"Updated executive vote status while maintaining thread context: {proposal.status}")
        else:
            tracker.update_proposal(
                proposal.id, 
                proposal.status, 
                current.get("thread_ts"),
                proposal_type=proposal.type,
                support=proposal.support
            )
            logger.warning(f"Failed to send alert, updated status only: {proposal.status}")
    elif current and current.get("status") != proposal.status:
        tracker.update_proposal(
            proposal.id, 
            proposal.status, 
            current.get("thread_ts"),
            proposal_type=proposal.type,
            support=proposal.support
        )
        logger.info(f"Updated proposal status without alert: {proposal.status}")

async def monitor_sky_proposals(
    slack_sender: Optional[SlackAlertSender] = None, 
    continuous: bool = False, 
    check_interval: Optional[int] = None,
    is_test_mode: Optional[bool] = None
):
    """Monitor Sky proposals and send alerts."""
    if continuous and check_interval is None:
        raise ValueError("check_interval is required when continuous is True")
        
    # For backward compatibility, derive is_test_mode from continuous if not provided
    is_test_mode = not continuous if is_test_mode is None else is_test_mode
        
    # Initialize components
    config = AlertConfig(
        slack_bot_token=settings.SLACK_BOT_TOKEN,
        app_slack_channel=settings.APP_SLACK_CHANNEL,
        net_slack_channel=settings.NET_SLACK_CHANNEL,
        test_slack_channel=settings.TEST_SLACK_CHANNEL,
        disable_link_previews=False,
        is_test_mode=is_test_mode
    )
    if slack_sender is None:
        slack_sender = SlackAlertSender(config)
    alert_handler = SkyAlertHandler(config)
    tracker = SkyProposalTracker(continuous=continuous, is_test_mode=is_test_mode)
    
    # Load watchlist
    sky_projects = await load_sky_watchlist()
    
    if not sky_projects:
        logger.warning("No Sky projects found in watchlist")
        return
    
    logger.info(f"Loaded {len(sky_projects)} Sky projects for monitoring")
    
    async with SkyClient() as client:
        while True:
            try:
                for project in sky_projects:
                    logger.info(f"Checking proposals for {project['name']}")
                    
                    try:
                        # First check active polls
                        polls = await client.get_polls()
                        logger.info(f"Found {len(polls)} active polls for {project['name']}")
                        
                        # Process active polls
                        for poll_data in polls:
                            proposal = client.parse_proposal(poll_data, "poll")
                            current = tracker.get_proposal(proposal.id, "poll")
                            await process_sky_proposal_alert(
                                proposal, project, current, alert_handler, slack_sender, tracker
                            )
                        
                        # Check status of tracked polls that are no longer active
                        # Create a copy of the keys to avoid modification during iteration
                        tracked_poll_keys = [key for key in tracker.proposals.keys() if key.startswith("poll:")]
                        for key in tracked_poll_keys:
                            data = tracker.proposals[key]
                            if data["status"] == "active":
                                poll_id = key.split(":")[1]
                                # Fetch the poll to check its current status
                                poll_data = await client.get_poll(poll_id)
                                if poll_data:
                                    proposal = client.parse_proposal(poll_data, "poll")
                                    await process_sky_proposal_alert(
                                        proposal, project, data, alert_handler, slack_sender, tracker
                                    )
                                else:
                                    # If poll not found, it's likely ended
                                    proposal = SkyProposal(
                                        id=poll_id,
                                        title="Unknown",  # We don't have the title anymore
                                        description="Unknown",
                                        status="ended",
                                        start_time=datetime.now(),
                                        end_time=datetime.now(),
                                        proposal_url=None,
                                        type="poll",
                                        support=None
                                    )
                                    await process_sky_proposal_alert(
                                        proposal, project, data, alert_handler, slack_sender, tracker
                                    )
                        
                        # Check executive votes
                        executive_votes = await client.get_executive_votes()
                        logger.info(f"Found {len(executive_votes)} executive votes for {project['name']}")
                        
                        for vote_data in executive_votes:
                            proposal = client.parse_proposal(vote_data, "executive")
                            current = tracker.get_proposal(proposal.id, "executive")
                            await process_sky_proposal_alert(
                                proposal, project, current, alert_handler, slack_sender, tracker
                            )
                            
                    except Exception as e:
                        logger.error(f"Error processing {project['name']}: {e}")
                        continue
                
                logger.info(f"Currently tracking {tracker.get_tracked_proposals_count()} proposals")
                
                if not continuous:
                    break
                    
                await asyncio.sleep(check_interval)
                
            except Exception as e:
                logger.error(f"Error monitoring proposals: {e}")
                await asyncio.sleep(60)

async def main():
    """Main entry point for Sky monitoring."""
    try:
        # Ensure test directory exists
        os.makedirs("data/test_proposal_tracking", exist_ok=True)
        
        # When running directly, use test mode
        await monitor_sky_proposals(continuous=False, is_test_mode=True)
    except KeyboardInterrupt:
        logger.info("Sky monitoring stopped by user")
    except Exception as e:
        logger.error(f"Sky monitoring stopped due to error: {e}")

if __name__ == "__main__":
    asyncio.run(main()) 