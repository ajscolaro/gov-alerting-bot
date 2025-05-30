import asyncio
import json
import logging
import os
import sys
from typing import Dict, Optional
from datetime import datetime, timedelta
from pathlib import Path

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.common.alerts.slack import SlackAlertSender
from src.common.alerts.base import AlertConfig
from src.integrations.tally.client import TallyClient, TallyProposal
from src.integrations.tally.alerts import TallyAlertHandler
from src.common.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_state_file_path() -> str:
    """Determine the appropriate state file path based on execution context."""
    # Check if we're being run directly (not through monitor.py)
    is_test_mode = os.path.basename(sys.argv[0]) in ["monitor_snapshot.py", "monitor_tally.py", "monitor_cosmos.py"]
    
    if is_test_mode:
        # Use test state file when running individually
        return "data/test_proposal_tracking/tally_proposal_state.json"
    else:
        # Use normal state file when running through monitor.py
        return "data/proposal_tracking/tally_proposal_state.json"

class TallyProposalTracker:
    """Tracks Tally proposals and their status changes with file-based persistence."""
    
    def __init__(self, continuous: bool = False):
        self.state_file = "data/test_proposal_tracking/tally_proposal_state.json" if not continuous else "data/proposal_tracking/tally_proposal_state.json"
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
    
    def get_proposal(self, proposal_id: str, project_id: Optional[str] = None) -> Optional[Dict]:
        """Get proposal by ID."""
        key = f"{project_id}:{proposal_id}" if project_id else proposal_id
        return self.proposals.get(key)
    
    def update_proposal(self, proposal_id: str, status: str, thread_ts: Optional[str] = None, 
                       alerted: bool = False, project_id: Optional[str] = None):
        """Update proposal status."""
        key = f"{project_id}:{proposal_id}" if project_id else proposal_id
        if key in self.proposals:
            self.proposals[key]["status"] = status
            if thread_ts:
                self.proposals[key]["thread_ts"] = thread_ts
            if alerted:
                self.proposals[key]["alerted"] = True
        else:
            self.proposals[key] = {
                "status": status,
                "thread_ts": thread_ts,
                "alerted": alerted
            }
        self._save_state()
    
    def remove_proposal(self, proposal_id: str, project_id: Optional[str] = None):
        """Remove proposal by ID."""
        key = f"{project_id}:{proposal_id}" if project_id else proposal_id
        if key in self.proposals:
            del self.proposals[key]
            self._save_state()
    
    def get_tracked_proposals_count(self) -> int:
        """Get the number of currently tracked proposals."""
        return len(self.proposals)

async def load_tally_watchlist():
    """Load the Tally watchlist from file."""
    try:
        with open("data/watchlists/tally_watchlist.json", "r") as f:
            data = json.load(f)
            projects = data.get("projects", [])
            
            # Validate required metadata fields
            for project in projects:
                required_fields = ["chain", "governor_address", "chain_id", "token_address", "tally_url"]
                for field in required_fields:
                    if field not in project["metadata"]:
                        logger.error(f"Missing required field '{field}' in project {project['name']}")
                        return []
            
            return projects
    except Exception as e:
        logger.error(f"Error loading Tally watchlist: {e}")
        return []

async def process_tally_proposal_alert(
    proposal: TallyProposal,
    project: Dict,
    current: Optional[Dict],
    alert_handler: TallyAlertHandler,
    slack_sender: SlackAlertSender,
    tracker: TallyProposalTracker
):
    """Process a Tally proposal alert."""
    previous_status = current["status"] if current else None
    
    if alert_handler.should_alert(proposal, previous_status):
        # Determine alert type
        if not previous_status:
            alert_type = "proposal_active"
        elif previous_status == "active" and proposal.status != "active":
            alert_type = "proposal_ended"
        else:
            # Skip other status changes
            return
        
        logger.info(f"Sending {alert_type} alert for {project['name']} proposal {proposal.id}")
        
        # Prepare alert data
        alert_data = {
            "project_name": project["name"],
            "proposal": proposal,
            "tally_url": project["metadata"]["tally_url"]
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
                logger.warning(f"No thread context found for proposal {proposal.id}")
        
        # Send the alert
        result = await slack_sender.send_alert(alert_handler, message)
        
        if result["ok"]:
            if alert_type == "proposal_active":
                tracker.update_proposal(proposal.id, proposal.status, result["ts"], True, project_id=project["name"])
                logger.info(f"Stored thread timestamp for new proposal: {result['ts']}")
            elif alert_type == "proposal_ended":
                final_statuses = {
                    "succeeded", "archived", "canceled", "callexecuted",
                    "defeated", "executed", "expired", "queued",
                    "pendingexecution", "crosschainexecuted"
                }
                
                if proposal.status.lower() in final_statuses:
                    tracker.remove_proposal(proposal.id, project_id=project["name"])
                    logger.info(f"Removed ended proposal from tracking: {proposal.id}")
                else:
                    tracker.update_proposal(proposal.id, proposal.status, current.get("thread_ts"), True, project_id=project["name"])
                    logger.info(f"Updated proposal status while maintaining thread context: {proposal.status}")
            else:
                tracker.update_proposal(proposal.id, proposal.status, current.get("thread_ts"), True, project_id=project["name"])
                logger.info(f"Updated proposal status while maintaining thread context: {proposal.status}")
        else:
            tracker.update_proposal(proposal.id, proposal.status, current.get("thread_ts"), project_id=project["name"])
            logger.warning(f"Failed to send alert, updated status only: {proposal.status}")
    elif current and current.get("status") != proposal.status:
        tracker.update_proposal(proposal.id, proposal.status, current.get("thread_ts"), project_id=project["name"])
        logger.info(f"Updated proposal status without alert: {proposal.status}")

async def monitor_tally_proposals(slack_sender: Optional[SlackAlertSender] = None, continuous: bool = False, check_interval: Optional[int] = None):
    """Monitor Tally proposals and send alerts.
    
    Args:
        slack_sender: Optional SlackAlertSender instance
        continuous: If True, runs in a continuous loop. If False, runs once and exits.
        check_interval: Number of seconds to wait between checks when running continuously.
                      Required if continuous is True, ignored otherwise.
    """
    if continuous and check_interval is None:
        raise ValueError("check_interval is required when continuous is True")
        
    # Initialize components
    config = AlertConfig(
        slack_bot_token=settings.SLACK_BOT_TOKEN,
        slack_channel=settings.TEST_SLACK_CHANNEL if not continuous else settings.SLACK_CHANNEL,
        disable_link_previews=False
    )
    if slack_sender is None:
        slack_sender = SlackAlertSender(config)
    alert_handler = TallyAlertHandler(config)
    tracker = TallyProposalTracker(continuous)
    
    # Load watchlist
    tally_projects = await load_tally_watchlist()
    
    if not tally_projects:
        logger.warning("No Tally projects found in watchlist")
        return
    
    logger.info(f"Loaded {len(tally_projects)} Tally projects for monitoring")
    
    async with TallyClient() as client:
        while True:
            try:
                for project in tally_projects:
                    logger.info(f"Checking proposals for {project['name']} ({project['metadata']['chain']})")
                    
                    try:
                        tally_metadata = project["metadata"]
                        proposals = await client.get_proposals(
                            tally_metadata["governor_address"],
                            tally_metadata["chain_id"]
                        )
                        
                        logger.info(f"Found {len(proposals)} proposals for {project['name']}")
                        
                        for proposal in proposals:
                            # Construct proposal URL
                            proposal.proposal_url = f"{tally_metadata['tally_url']}/proposal/{proposal.id}"
                            
                            current = tracker.get_proposal(proposal.id, project_id=project["name"])
                            await process_tally_proposal_alert(
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
    """Main entry point for Tally monitoring."""
    try:
        # Ensure test directory exists
        os.makedirs("data/test_proposal_tracking", exist_ok=True)
        
        await monitor_tally_proposals(continuous=False)
    except KeyboardInterrupt:
        logger.info("Tally monitoring stopped by user")
    except Exception as e:
        logger.error(f"Tally monitoring stopped due to error: {e}")

if __name__ == "__main__":
    asyncio.run(main()) 