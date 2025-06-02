import os
import sys
import json
import asyncio
import logging
from typing import Dict, Set, Optional
from datetime import datetime

# Add project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.integrations.snapshot.client import SnapshotClient
from src.integrations.snapshot.alerts import SnapshotAlertHandler
from src.common.alerts.slack import SlackAlertSender
from src.common.alerts.base import AlertConfig
from src.common.config import settings

logger = logging.getLogger(__name__)

# Rate limiting constants
SNAPSHOT_RATE_LIMIT = 1  # requests per second (reduced from 30)
RATE_LIMIT_WINDOW = 1.0   # seconds
MAX_RETRIES = 3          # maximum number of retries for rate limit errors
INITIAL_BACKOFF = 2.0    # initial backoff time in seconds (increased from 1.0)

class RateLimiter:
    """Rate limiter for API requests."""
    
    def __init__(self, rate_limit: int, window: float):
        self.rate_limit = rate_limit
        self.window = window
        self.semaphore = asyncio.Semaphore(rate_limit)
        self.last_reset = datetime.now()
        self.requests_this_window = 0
        self.consecutive_failures = 0
    
    async def acquire(self):
        """Acquire a rate limit token with exponential backoff."""
        now = datetime.now()
        time_since_reset = (now - self.last_reset).total_seconds()
        
        # Reset counter if window has passed
        if time_since_reset >= self.window:
            self.requests_this_window = 0
            self.last_reset = now
            self.consecutive_failures = 0  # Reset failure counter on window reset
        
        # If we've hit the limit, wait until the window resets
        if self.requests_this_window >= self.rate_limit:
            wait_time = self.window - time_since_reset
            if wait_time > 0:
                logger.debug(f"Rate limit reached, waiting {wait_time:.2f} seconds")
                await asyncio.sleep(wait_time)
            self.requests_this_window = 0
            self.last_reset = datetime.now()
        
        # Acquire semaphore and increment counter
        await self.semaphore.acquire()
        self.requests_this_window += 1
    
    def release(self):
        """Release a rate limit token."""
        self.semaphore.release()
    
    async def handle_rate_limit_error(self):
        """Handle rate limit error with exponential backoff."""
        self.consecutive_failures += 1
        if self.consecutive_failures > MAX_RETRIES:
            logger.error("Max retries exceeded for rate limit errors")
            return False
            
        backoff_time = INITIAL_BACKOFF * (2 ** (self.consecutive_failures - 1))
        logger.warning(f"Rate limit error, backing off for {backoff_time:.2f} seconds")
        await asyncio.sleep(backoff_time)
        return True

class SnapshotProposalTracker:
    """Tracks Snapshot proposals and their status changes with file-based persistence."""
    
    def __init__(self, continuous: bool = False):
        self.state_file = "data/test_proposal_tracking/snapshot_proposal_state.json" if not continuous else "data/proposal_tracking/snapshot_proposal_state.json"
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
    
    def get_all_proposals(self) -> Dict[str, Dict]:
        """Get all tracked proposals."""
        return self.proposals
    
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

class SpaceAlertTracker:
    """Tracks which spaces we've already alerted about."""
    
    def __init__(self, continuous: bool = False):
        self.state_file = "data/test_proposal_tracking/admin_alerts.json" if not continuous else "data/proposal_tracking/admin_alerts.json"
        self.alerted_spaces: Dict[str, bool] = self._load_state()
        logger.info(f"Loaded admin alerts from {self.state_file}: {len(self.alerted_spaces)} spaces")
    
    def _load_state(self) -> Dict[str, bool]:
        """Load space alert state from file."""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, "r") as f:
                    data = json.load(f)
                    return data.get("alerted_items", {}).get("snapshot_spaces", {})
            return {}
        except Exception as e:
            logger.error(f"Error loading admin alerts: {e}")
            return {}
    
    def _save_state(self):
        """Save current space alert state to file."""
        try:
            os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
            # Load existing data to preserve other alert types
            existing_data = {}
            if os.path.exists(self.state_file):
                with open(self.state_file, "r") as f:
                    existing_data = json.load(f)
            
            # Update only our section while preserving others
            alerted_items = existing_data.get("alerted_items", {})
            alerted_items["snapshot_spaces"] = self.alerted_spaces
            
            with open(self.state_file, "w") as f:
                json.dump({"alerted_items": alerted_items}, f, indent=2)
            logger.info(f"Saved admin alerts to {self.state_file}")
        except Exception as e:
            logger.error(f"Error saving admin alerts: {e}")
    
    def has_alerted(self, space_id: str) -> bool:
        """Check if we've already alerted about a space."""
        return self.alerted_spaces.get(space_id, False)
    
    def mark_alerted(self, space_id: str):
        """Mark a space as alerted."""
        self.alerted_spaces[space_id] = True
        self._save_state()

async def load_snapshot_watchlist():
    """Load the Snapshot watchlist from file."""
    try:
        with open("data/watchlists/snapshot_watchlist.json", "r") as f:
            data = json.load(f)
            projects = data.get("projects", [])
            
            # Validate required metadata fields
            for project in projects:
                required_fields = ["space", "snapshot_url"]
                for field in required_fields:
                    if field not in project["metadata"]:
                        logger.error(f"Missing required field '{field}' in project {project['name']}")
                        return []
            
            return projects
    except Exception as e:
        logger.error(f"Error loading Snapshot watchlist: {e}")
        return []

async def process_snapshot_proposal_alert(
    proposal: Dict,
    project: Dict,
    previous_status: Optional[str],
    alert_handler: SnapshotAlertHandler,
    alert_sender: SlackAlertSender,
    snapshot_url: str,
    thread_ts: Optional[str] = None,
    tracker: Optional[SnapshotProposalTracker] = None,
    proposal_id: Optional[str] = None,
    alert_type: Optional[str] = None
) -> Optional[Dict]:
    """Process a Snapshot proposal alert."""
    try:
        # Log full proposal state for debugging
        logger.info(f"Processing alert for proposal {proposal_id} (project: {project['name']})")
        logger.info(f"Current state: {proposal.get('state')}, Previous state: {previous_status}")
        logger.info(f"Thread TS: {thread_ts}")
        
        # Determine alert type if not provided
        if not alert_type:
            if not previous_status:
                alert_type = "proposal_active"
            elif proposal.get("state") == "deleted":
                alert_type = "proposal_deleted"
            elif previous_status == "active" and proposal["state"] == "closed":
                alert_type = "proposal_ended"
            else:
                logger.info(f"No alert needed - state change from {previous_status} to {proposal.get('state')} not handled")
                return None
            
        # Check if we should send an alert
        should_alert = alert_handler.should_alert(proposal, previous_status, alert_type=alert_type)
        logger.info(f"Should alert check for {alert_type}: {should_alert}")
        
        if should_alert:
            logger.info(f"Preparing to send {alert_type} alert for {project['name']} proposal {proposal.get('id', 'invalid space')}")
            
            # For space_not_detected alerts, ensure proposal has space field
            if alert_type == "space_not_detected" and "space" not in proposal:
                proposal["space"] = project["metadata"]["space"]
            
            # Format and send the alert
            alert_data = {
                "project_name": project["name"],
                "proposal": proposal,
                "snapshot_url": snapshot_url
            }
            
            # Format the alert message
            message = alert_handler.format_alert(alert_type, alert_data)
            
            # Handle thread context for non-active alerts
            if alert_type != "proposal_active" and alert_type != "space_not_detected":
                if thread_ts:
                    message["thread_ts"] = thread_ts
                    message["reply_broadcast"] = True
                    logger.info(f"Sending {alert_type} as thread reply with ts: {thread_ts}")
                else:
                    message["text"] = f"⚠️ Unable to find original message context. {message['text']}"
                    logger.warning(f"No thread context found for proposal {proposal_id}")
            
            # Send the alert using the slack sender
            try:
                result = await alert_sender.send_alert(alert_handler, message)
                
                if result and result.get("ok"):
                    logger.info(f"Successfully sent {alert_type} alert for proposal {proposal_id}")
                    logger.info(f"Alert result: {result}")
                    
                    # Update proposal state if needed
                    if tracker and proposal_id and alert_type != "space_not_detected":
                        logger.info(f"Updating state for proposal {proposal_id} to {proposal['state']}")
                        if alert_type == "proposal_active":
                            # For new active proposals, store the thread timestamp
                            tracker.update_proposal(
                                proposal_id,
                                proposal["state"],
                                result["ts"],
                                True,
                                project_id=project["metadata"]["space"]
                            )
                        elif alert_type == "proposal_ended":
                            # For ended proposals, remove from tracking
                            tracker.remove_proposal(proposal_id, project_id=project["metadata"]["space"])
                        else:
                            # For other alerts (like deleted), update status but keep thread context
                            tracker.update_proposal(
                                proposal_id,
                                proposal["state"],
                                thread_ts,  # Keep existing thread context
                                True,
                                project_id=project["metadata"]["space"]
                            )
                else:
                    logger.error(f"Failed to send alert for proposal {proposal_id}")
                    logger.error(f"Alert result: {result}")
                    # Don't update state if alert failed
                
                return result
                
            except Exception as e:
                logger.error(f"Error sending alert for proposal {proposal_id}: {str(e)}")
                return None
            
    except Exception as e:
        logger.error(f"Error processing alert for proposal {proposal_id}: {str(e)}")
        return None

async def check_proposals(
    client: SnapshotClient,
    tracker: SnapshotProposalTracker,
    space_tracker: SpaceAlertTracker,
    alert_handler: SnapshotAlertHandler,
    alert_sender: SlackAlertSender,
    snapshot_url: Optional[str],
    rate_limiter: RateLimiter
) -> None:
    """Check all tracked proposals for updates."""
    try:
        # Get all tracked proposals and create a copy of the keys
        proposals = tracker.get_all_proposals()
        proposal_keys = list(proposals.keys())  # Create a copy of keys to iterate over
        logger.info(f"Checking {len(proposals)} tracked proposals")
        
        # Log all tracked proposals for debugging
        for pid, pdata in proposals.items():
            logger.info(f"Tracked proposal: {pid} - State: {pdata.get('status')}, Thread: {pdata.get('thread_ts')}")
        
        # Load watchlist to get project objects
        snapshot_projects = await load_snapshot_watchlist()
        project_map = {p["metadata"]["space"]: p for p in snapshot_projects}
        
        # Then process existing proposals as before
        for proposal_id in proposal_keys:
            try:
                proposal_data = proposals[proposal_id]
                logger.info(f"Processing proposal {proposal_id} - Current state: {proposal_data.get('status')}")
                
                # Acquire rate limit token
                await rate_limiter.acquire()
                
                try:
                    # Extract space and proposal ID from the key
                    space, actual_proposal_id = proposal_id.split(":", 1) if ":" in proposal_id else (None, proposal_id)
                    
                    if not space or space not in project_map:
                        logger.error(f"Could not find project for space {space}")
                        continue
                        
                    project = project_map[space]
                    
                    # Get current proposal state
                    current_proposal = await client.get_proposal(actual_proposal_id)
                    
                    if not current_proposal:
                        logger.info(f"Proposal {proposal_id} was deleted - current state: {proposal_data.get('status')}")
                        deleted_proposal = {
                            "id": actual_proposal_id,
                            "state": "deleted",
                            "title": proposal_data.get("title", "Unknown Proposal")
                        }
                        
                        # Process the alert
                        result = await process_snapshot_proposal_alert(
                            proposal=deleted_proposal,
                            project=project,
                            previous_status=proposal_data["status"],
                            alert_handler=alert_handler,
                            alert_sender=alert_sender,
                            snapshot_url=project["metadata"]["snapshot_url"],
                            thread_ts=proposal_data.get("thread_ts"),
                            tracker=tracker,
                            proposal_id=actual_proposal_id,
                            alert_type="proposal_deleted"
                        )
                        
                        # Only remove deleted proposal if alert was sent successfully
                        if result and result.get("ok"):
                            logger.info(f"Successfully sent delete alert for {proposal_id}, removing from state")
                            tracker.remove_proposal(actual_proposal_id, project_id=space)
                        else:
                            logger.warning(f"Failed to send delete alert for {proposal_id}, keeping in state. Result: {result}")
                        continue
                    
                    # Check if proposal state has changed
                    if current_proposal["state"] != proposal_data["status"]:
                        logger.info(f"State change detected for {proposal_id}: {proposal_data['status']} -> {current_proposal['state']}")
                        
                        # Process the alert
                        result = await process_snapshot_proposal_alert(
                            proposal=current_proposal,
                            project=project,
                            previous_status=proposal_data["status"],
                            alert_handler=alert_handler,
                            alert_sender=alert_sender,
                            snapshot_url=project["metadata"]["snapshot_url"],
                            thread_ts=proposal_data.get("thread_ts"),
                            tracker=tracker,
                            proposal_id=actual_proposal_id,
                            alert_type="proposal_ended"
                        )
                        
                        # Only update state and remove proposal if alert was sent successfully
                        if result and result.get("ok"):
                            if current_proposal["state"] == "closed":
                                logger.info(f"Successfully sent end alert for {proposal_id}, removing from state")
                                tracker.remove_proposal(actual_proposal_id, project_id=space)
                            else:
                                logger.info(f"Successfully sent state change alert for {proposal_id}, updating state")
                                tracker.update_proposal(
                                    actual_proposal_id,
                                    current_proposal["state"],
                                    result["ts"],
                                    True,
                                    project_id=space
                                )
                        else:
                            logger.warning(f"Failed to send state change alert for {proposal_id}, keeping current state. Result: {result}")
                    else:
                        logger.debug(f"No state change for proposal {proposal_id} - still {current_proposal['state']}")
                    
                except Exception as e:
                    if "Too Many Requests" in str(e):
                        logger.warning("Rate limit exceeded, waiting before retrying...")
                        await asyncio.sleep(60)  # Wait a minute before retrying
                    else:
                        logger.error(f"Error processing proposal {proposal_id}: {e}")
                finally:
                    # Always release the rate limit token
                    rate_limiter.release()
                
            except Exception as e:
                logger.error(f"Error processing proposal {proposal_id}: {e}")
                continue
                
        # Now, check for new proposals for each project as usual
        for project in snapshot_projects:
            space = project["metadata"]["space"]
            # Skip if we've already alerted about this space being invalid
            if space_tracker.has_alerted(space):
                continue
            logger.info(f"Checking proposals for {project['name']}")
            try:
                # Acquire rate limit token
                await rate_limiter.acquire()
                try:
                    proposals = await client.get_active_proposals(space)
                    
                    if proposals is None:
                        # Space doesn't exist - send alert and mark as alerted
                        logger.warning(f"Space {space} not found for {project['name']}")
                        if not space_tracker.has_alerted(space):
                            result = await process_snapshot_proposal_alert(
                                proposal={"id": "invalid", "state": "invalid", "title": "Invalid Space"},
                                project=project,
                                previous_status=None,
                                alert_handler=alert_handler,
                                alert_sender=alert_sender,
                                snapshot_url=project["metadata"]["snapshot_url"],
                                thread_ts=None,
                                tracker=tracker,
                                proposal_id=None,
                                alert_type="space_not_detected"
                            )
                            if result and result.get("ok"):
                                space_tracker.mark_alerted(space)
                        continue
                        
                    logger.info(f"Found {len(proposals)} proposals for {project['name']}")
                    
                    for proposal in proposals:
                        current = tracker.get_proposal(proposal["id"], project_id=space)
                        result = await process_snapshot_proposal_alert(
                            proposal=proposal,
                            project=project,  # Pass the full project object
                            previous_status=current["status"] if current else None,
                            alert_handler=alert_handler,
                            alert_sender=alert_sender,
                            snapshot_url=project["metadata"]["snapshot_url"],
                            thread_ts=current.get("thread_ts") if current else None,
                            tracker=tracker,
                            proposal_id=proposal["id"]
                        )
                finally:
                    # Always release the rate limit token
                    rate_limiter.release()
            except Exception as e:
                logger.error(f"Error processing {project['name']}: {e}")
                continue
    except Exception as e:
        logger.error(f"Error in check_proposals: {e}")
        raise

async def monitor_snapshot_proposals(slack_sender: Optional[SlackAlertSender] = None, continuous: bool = False, check_interval: Optional[int] = None):
    """Monitor Snapshot proposals and send alerts."""
    try:
        if continuous and check_interval is None:
            raise ValueError("check_interval is required when continuous is True")
            
        # Initialize components
        tracker = SnapshotProposalTracker(continuous)
        space_tracker = SpaceAlertTracker(continuous)
        
        # Create alert config
        config = AlertConfig(
            slack_bot_token=settings.SLACK_BOT_TOKEN,
            slack_channel=settings.TEST_SLACK_CHANNEL if not continuous else settings.SLACK_CHANNEL,
            disable_link_previews=False
        )
        
        # Initialize alert handler with config
        alert_handler = SnapshotAlertHandler(config)
        rate_limiter = RateLimiter(SNAPSHOT_RATE_LIMIT, RATE_LIMIT_WINDOW)
        
        # Load watchlist
        snapshot_projects = await load_snapshot_watchlist()
        if not snapshot_projects:
            logger.error("No valid projects found in watchlist")
            return
            
        logger.info(f"Loaded {len(snapshot_projects)} projects from watchlist")
        
        # Create Slack sender if not provided
        if not slack_sender:
            slack_sender = SlackAlertSender(config)
        
        async with SnapshotClient() as client:
            while True:
                try:
                    # First check existing proposals for updates/deletions and validate spaces
                    await check_proposals(client, tracker, space_tracker, alert_handler, slack_sender, None, rate_limiter)
                    
                    # Then check for new proposals
                    for project in snapshot_projects:
                        # Skip if we've already alerted about this space being invalid
                        if space_tracker.has_alerted(project["metadata"]["space"]):
                            continue
                            
                        logger.info(f"Checking proposals for {project['name']}")
                        
                        try:
                            # Acquire rate limit token
                            await rate_limiter.acquire()
                            
                            try:
                                proposals = await client.get_active_proposals(project["metadata"]["space"])
                                
                                if proposals is None:
                                    # Space doesn't exist - send alert and mark as alerted
                                    logger.warning(f"Space {project['metadata']['space']} not found for {project['name']}")
                                    if not space_tracker.has_alerted(project["metadata"]["space"]):
                                        result = await process_snapshot_proposal_alert(
                                            proposal={"id": "invalid", "state": "invalid", "title": "Invalid Space"},
                                            project=project,
                                            previous_status=None,
                                            alert_handler=alert_handler,
                                            alert_sender=slack_sender,
                                            snapshot_url=project["metadata"]["snapshot_url"],
                                            thread_ts=None,
                                            tracker=tracker,
                                            proposal_id=None,
                                            alert_type="space_not_detected"
                                        )
                                        if result and result.get("ok"):
                                            space_tracker.mark_alerted(project["metadata"]["space"])
                                    continue
                                    
                                logger.info(f"Found {len(proposals)} proposals for {project['name']}")
                                
                                for proposal in proposals:
                                    current = tracker.get_proposal(proposal["id"], project_id=project["metadata"]["space"])
                                    result = await process_snapshot_proposal_alert(
                                        proposal=proposal,
                                        project=project,  # Pass the full project object
                                        previous_status=current["status"] if current else None,
                                        alert_handler=alert_handler,
                                        alert_sender=slack_sender,
                                        snapshot_url=project["metadata"]["snapshot_url"],
                                        thread_ts=current.get("thread_ts") if current else None,
                                        tracker=tracker,
                                        proposal_id=proposal["id"]
                                    )
                                    
                            finally:
                                # Always release the rate limit token
                                rate_limiter.release()
                                
                        except Exception as e:
                            logger.error(f"Error processing {project['name']}: {e}")
                            continue
                    
                    logger.info(f"Currently tracking {tracker.get_tracked_proposals_count()} proposals")
                    
                    if not continuous:
                        break
                        
                    # Wait for the configured interval before next check
                    await asyncio.sleep(check_interval)
                    
                except Exception as e:
                    logger.error(f"Error monitoring proposals: {e}")
                    if continuous:
                        await asyncio.sleep(60)  # Wait a minute before retrying on error
                    else:
                        break
                        
    except Exception as e:
        logger.error(f"Error in monitor_snapshot_proposals: {e}")
        raise

async def main():
    """Main entry point for Snapshot monitoring."""
    try:
        # Ensure test directory exists
        os.makedirs("data/test_proposal_tracking", exist_ok=True)
        
        await monitor_snapshot_proposals(continuous=False)
    except KeyboardInterrupt:
        logger.info("Snapshot monitoring stopped by user")
    except Exception as e:
        logger.error(f"Snapshot monitoring stopped due to error: {e}")

if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Run monitor
    asyncio.run(main()) 