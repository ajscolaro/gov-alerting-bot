import asyncio
import json
import logging
import os
import sys
from typing import Dict, Optional
from datetime import datetime, timedelta
from pathlib import Path
import aiohttp

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.common.alerts.slack import SlackAlertSender
from src.common.alerts.base import AlertConfig
from src.integrations.xrpl.client import XRPLClient, XRPLAmendment
from src.integrations.xrpl.alerts import XRPLAlertHandler
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
    is_test_mode = os.path.basename(sys.argv[0]) in ["monitor_snapshot.py", "monitor_tally.py", "monitor_cosmos.py", "monitor_sky.py", "monitor_xrpl.py"]
    
    if is_test_mode:
        # Use test state file when running individually
        return "data/test_proposal_tracking/xrpl_proposal_state.json"
    else:
        # Use normal state file when running through monitor.py
        return "data/proposal_tracking/xrpl_proposal_state.json"

class XRPLAmendmentTracker:
    """Tracks XRPL amendments and their status changes with file-based persistence."""
    
    def __init__(self, continuous: bool = False, is_test_mode: Optional[bool] = None):
        # For backward compatibility, derive is_test_mode from continuous if not provided
        self.is_test_mode = not continuous if is_test_mode is None else is_test_mode
        self.state_file = "data/test_proposal_tracking/xrpl_proposal_state.json" if self.is_test_mode else "data/proposal_tracking/xrpl_proposal_state.json"
        self.amendments: Dict[str, Dict] = self._load_state()
        logger.info(f"Loaded state from {self.state_file}: {len(self.amendments)} amendments")
    
    def _load_state(self) -> Dict[str, Dict]:
        """Load amendment state from file."""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, "r") as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logger.error(f"Error loading amendment state: {e}")
            return {}
    
    def _save_state(self):
        """Save current amendment state to file."""
        try:
            os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
            with open(self.state_file, "w") as f:
                json.dump(self.amendments, f, indent=2)
            logger.info(f"Saved state to {self.state_file}")
        except Exception as e:
            logger.error(f"Error saving amendment state: {e}")
    
    def get_amendment(self, amendment_id: str) -> Optional[Dict]:
        """Get amendment by ID."""
        return self.amendments.get(amendment_id)
    
    def update_amendment(self, amendment_id: str, enabled: bool, thread_ts: Optional[str] = None, 
                        alerted: bool = False):
        """Update amendment status."""
        if amendment_id in self.amendments:
            self.amendments[amendment_id]["enabled"] = enabled
            if thread_ts:
                self.amendments[amendment_id]["thread_ts"] = thread_ts
            if alerted:
                self.amendments[amendment_id]["alerted"] = True
        else:
            self.amendments[amendment_id] = {
                "enabled": enabled,
                "thread_ts": thread_ts,
                "alerted": alerted
            }
        self._save_state()
    
    def remove_amendment(self, amendment_id: str):
        """Remove amendment by ID."""
        if amendment_id in self.amendments:
            del self.amendments[amendment_id]
            self._save_state()
    
    def get_tracked_amendments_count(self) -> int:
        """Get the number of currently tracked amendments."""
        return len(self.amendments)

async def load_xrpl_watchlist():
    """Load the XRPL watchlist from file."""
    try:
        with open("data/watchlists/xrpl_watchlist.json", "r") as f:
            data = json.load(f)
            return data.get("projects", [])
    except Exception as e:
        logger.error(f"Error loading XRPL watchlist: {e}")
        return []

async def process_xrpl_amendment_alert(
    amendment: XRPLAmendment,
    network: Dict,
    current: Optional[Dict],
    alert_handler: XRPLAlertHandler,
    slack_sender: SlackAlertSender,
    tracker: XRPLAmendmentTracker,
    client: XRPLClient
):
    """Process an XRPL amendment alert."""
    previous_enabled = current["enabled"] if current else None
    
    if alert_handler.should_alert(amendment, previous_enabled):
        # Determine alert type
        if previous_enabled is None:
            alert_type = "amendment_active"
        elif not previous_enabled and amendment.enabled and amendment.enabled_on:
            alert_type = "amendment_ended"
        else:
            # Skip other status changes
            return
        
        logger.info(f"Sending {alert_type} alert for {network['name']} amendment {amendment.amendment_id}")
        
        # Prepare alert data
        alert_data = {
            "network_name": network["name"],
            "amendment": amendment,
            "amendment_url": client.get_amendment_url(amendment.amendment_id)
        }
        
        # Format and send alert
        message = alert_handler.format_alert(alert_type, alert_data)
        
        # Handle thread context
        if alert_type != "amendment_active":
            if current and current.get("thread_ts"):
                message["thread_ts"] = current["thread_ts"]
                logger.info(f"Sending {alert_type} as thread reply with ts: {current['thread_ts']}")
            else:
                message["text"] = f"⚠️ Unable to find original message context. {message['text']}"
                logger.warning(f"No thread context found for amendment {amendment.amendment_id}")
        
        # Get intel_label from network metadata
        intel_label = network.get("intel_label")
        
        # Send the alert with timeout and intel_label
        try:
            async with asyncio.timeout(30):  # 30 second timeout for Slack API calls
                result = await slack_sender.send_alert(alert_handler, message, intel_label=intel_label)
        except asyncio.TimeoutError:
            logger.error(f"Timeout sending alert for {network['name']} amendment {amendment.amendment_id}")
            return
        
        if result["ok"]:
            if alert_type == "amendment_active":
                tracker.update_amendment(amendment.amendment_id, amendment.enabled, result["ts"], True)
                logger.info(f"Stored thread timestamp for new amendment: {result['ts']}")
            elif alert_type == "amendment_ended":
                tracker.remove_amendment(amendment.amendment_id)
                logger.info(f"Removed ended amendment from tracking: {amendment.amendment_id}")
        else:
            tracker.update_amendment(amendment.amendment_id, amendment.enabled, current.get("thread_ts") if current else None)
            logger.warning(f"Failed to send alert, updated status only: {amendment.enabled}")
    elif current and current.get("enabled") != amendment.enabled:
        tracker.update_amendment(amendment.amendment_id, amendment.enabled, current.get("thread_ts"))
        logger.info(f"Updated amendment status without alert: {amendment.enabled}")

async def monitor_xrpl_amendments(
    slack_sender: Optional[SlackAlertSender] = None, 
    continuous: bool = False, 
    check_interval: Optional[int] = None,
    is_test_mode: Optional[bool] = None
):
    """Monitor XRPL amendments and send alerts.
    
    Args:
        slack_sender: SlackAlertSender instance for sending alerts
        continuous: Whether to run continuously or just once
        check_interval: Interval between checks in seconds
        is_test_mode: Whether to run in test mode
    """
    # For backward compatibility, derive is_test_mode from continuous if not provided
    if is_test_mode is None:
        is_test_mode = not continuous
    
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
    
    alert_handler = XRPLAlertHandler(config)
    tracker = XRPLAmendmentTracker(continuous=continuous, is_test_mode=is_test_mode)
    
    # Load watchlist
    networks = await load_xrpl_watchlist()
    if not networks:
        logger.warning("No XRPL networks found in watchlist")
        return
    
    logger.info(f"Loaded {len(networks)} XRPL networks from watchlist")
    
    # For XRPL, we only have one network (the mainnet)
    network = networks[0] if networks else {"name": "XRPL", "intel_label": "net", "metadata": {}}
    
    # Initialize XRPL client with metadata from watchlist
    async with XRPLClient(metadata=network.get("metadata", {})) as client:
        while True:
            try:
                logger.info("Starting XRPL amendments check...")
                
                # Get tracked amendments for status checking
                tracked_amendments = tracker.amendments
                
                # Fetch amendments
                amendments = await client.get_amendments(tracked_amendments)
                
                if not amendments:
                    logger.info("No amendments found")
                else:
                    logger.info(f"Processing {len(amendments)} amendments")
                    
                    # Process each amendment
                    for amendment in amendments:
                        # Get current state
                        current = tracker.get_amendment(amendment.amendment_id)
                        
                        # Process alert
                        await process_xrpl_amendment_alert(
                            amendment, network, current, alert_handler, slack_sender, tracker, client
                        )
                
                logger.info(f"XRPL amendments check completed. Tracking {tracker.get_tracked_amendments_count()} amendments")
                
                if not continuous:
                    break
                
                # Wait before next check
                interval = check_interval or settings.CHECK_INTERVAL
                logger.info(f"Waiting {interval} seconds before next check...")
                await asyncio.sleep(interval)
                
            except Exception as e:
                logger.error(f"Error in XRPL amendments monitoring loop: {e}")
                if not continuous:
                    break
                await asyncio.sleep(60)  # Wait 1 minute before retrying

async def main():
    """Main function for running the XRPL monitor directly."""
    # Determine if we're in test mode based on script name
    is_test_mode = os.path.basename(sys.argv[0]) == "monitor_xrpl.py"
    
    if is_test_mode:
        logger.info("Running XRPL monitor in test mode")
        await monitor_xrpl_amendments(continuous=False, is_test_mode=True)
    else:
        logger.info("Running XRPL monitor in production mode")
        await monitor_xrpl_amendments(continuous=True, is_test_mode=False)

if __name__ == "__main__":
    asyncio.run(main()) 