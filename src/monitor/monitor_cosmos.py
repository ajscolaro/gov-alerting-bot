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
from src.integrations.cosmos.client import CosmosClient, CosmosProposal
from src.integrations.cosmos.alerts import CosmosAlertHandler
from src.common.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class CosmosProposalTracker:
    """Tracks Cosmos proposals and their status changes with file-based persistence."""
    
    def __init__(self, state_file: str = "data/proposal_tracking/cosmos_proposal_state.json"):
        self.state_file = state_file
        self.proposals: Dict[str, Dict] = self._load_state()
        logger.info(f"Loaded state from {state_file}: {len(self.proposals)} proposals")
    
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
    
    def get_proposal(self, proposal_id: str, network_id: Optional[str] = None) -> Optional[Dict]:
        """Get proposal by ID."""
        key = f"{network_id}:{proposal_id}" if network_id else proposal_id
        return self.proposals.get(key)
    
    def update_proposal(self, proposal_id: str, status: str, thread_ts: Optional[str] = None, 
                       alerted: bool = False, network_id: Optional[str] = None):
        """Update proposal status."""
        key = f"{network_id}:{proposal_id}" if network_id else proposal_id
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
    
    def remove_proposal(self, proposal_id: str, network_id: Optional[str] = None):
        """Remove proposal by ID."""
        key = f"{network_id}:{proposal_id}" if network_id else proposal_id
        if key in self.proposals:
            del self.proposals[key]
            self._save_state()
    
    def get_tracked_proposals_count(self) -> int:
        """Get the number of currently tracked proposals."""
        return len(self.proposals)

async def load_cosmos_watchlist():
    """Load the Cosmos watchlist from file."""
    try:
        with open("data/watchlists/cosmos_watchlist.json", "r") as f:
            data = json.load(f)
            return data.get("projects", [])
    except Exception as e:
        logger.error(f"Error loading Cosmos watchlist: {e}")
        return []

async def process_cosmos_proposal_alert(
    proposal: CosmosProposal,
    network: Dict,
    current: Optional[Dict],
    alert_handler: CosmosAlertHandler,
    slack_sender: SlackAlertSender,
    tracker: CosmosProposalTracker
):
    """Process a Cosmos proposal alert."""
    previous_status = current["status"] if current else None
    
    if alert_handler.should_alert(proposal, previous_status):
        # Determine alert type
        if not previous_status:
            alert_type = "proposal_voting"
        elif previous_status == "PROPOSAL_STATUS_VOTING_PERIOD" and proposal.status != "PROPOSAL_STATUS_VOTING_PERIOD":
            alert_type = "proposal_ended"
        else:
            # Skip other status changes
            return
        
        logger.info(f"Sending {alert_type} alert for {network['name']} proposal {proposal.id}")
        
        # Prepare alert data
        alert_data = {
            "network_name": network["name"],
            "proposal": proposal,
            "explorer_type": network["metadata"].get("explorer_type", "mintscan"),
            "explorer_name": network["metadata"].get("explorer_name", "Mintscan")
        }
        
        # Format and send alert
        message = alert_handler.format_alert(alert_type, alert_data)
        
        # Handle thread context
        if alert_type != "proposal_voting":
            if current and current.get("thread_ts"):
                message["thread_ts"] = current["thread_ts"]
                logger.info(f"Sending {alert_type} as thread reply with ts: {current['thread_ts']}")
            else:
                message["text"] = f"⚠️ Unable to find original message context. {message['text']}"
                logger.warning(f"No thread context found for proposal {proposal.id}")
        
        # Send the alert with timeout
        try:
            async with asyncio.timeout(30):  # 30 second timeout for Slack API calls
                result = await slack_sender.send_alert(alert_handler, message)
        except asyncio.TimeoutError:
            logger.error(f"Timeout sending alert for {network['name']} proposal {proposal.id}")
            return
        
        if result["ok"]:
            if alert_type == "proposal_voting":
                tracker.update_proposal(proposal.id, proposal.status, result["ts"], True, network_id=network["name"])
                logger.info(f"Stored thread timestamp for new proposal: {result['ts']}")
            elif alert_type == "proposal_ended":
                final_statuses = {
                    "PROPOSAL_STATUS_PASSED",
                    "PROPOSAL_STATUS_REJECTED",
                    "PROPOSAL_STATUS_FAILED"
                }
                
                if proposal.status in final_statuses:
                    tracker.remove_proposal(proposal.id, network_id=network["name"])
                    logger.info(f"Removed ended proposal from tracking: {proposal.id}")
                else:
                    tracker.update_proposal(proposal.id, proposal.status, current.get("thread_ts"), True, network_id=network["name"])
                    logger.info(f"Updated proposal status while maintaining thread context: {proposal.status}")
        else:
            tracker.update_proposal(proposal.id, proposal.status, current.get("thread_ts"), network_id=network["name"])
            logger.warning(f"Failed to send alert, updated status only: {proposal.status}")
    elif current and current.get("status") != proposal.status:
        tracker.update_proposal(proposal.id, proposal.status, current.get("thread_ts"), network_id=network["name"])
        logger.info(f"Updated proposal status without alert: {proposal.status}")

async def monitor_cosmos_proposals(slack_sender: Optional[SlackAlertSender] = None, continuous: bool = False, check_interval: Optional[int] = None):
    """Monitor Cosmos proposals and send alerts.
    
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
    alert_handler = CosmosAlertHandler(config)
    tracker = CosmosProposalTracker()
    
    # Load watchlist
    cosmos_networks = await load_cosmos_watchlist()
    
    if not cosmos_networks:
        logger.warning("No Cosmos networks found in watchlist")
        return
    
    # Initialize clients for each chain
    clients = {}
    for network in cosmos_networks:
        metadata = network["metadata"]
        chain_id = metadata["chain_id"]
        base_url = metadata["rpc_url"]
        explorer_url = metadata.get("explorer_url")
        explorer_type = metadata.get("explorer_type", "mintscan")
        fallback_url = metadata.get("fallback_rpc_url")
        
        # Create client with appropriate explorer type and fallback URL
        client = CosmosClient(
            base_url=base_url,
            chain_id=chain_id,
            explorer_url=explorer_url,
            explorer_type=explorer_type,
            fallback_url=fallback_url
        )
        
        clients[chain_id] = client
    
    while True:
        try:
            for network in cosmos_networks:
                logger.info(f"Checking proposals for {network['name']}")
                
                try:
                    metadata = network["metadata"]
                    async with clients[metadata["chain_id"]] as client:
                        # Increase timeout to 60 seconds to allow for fallback attempts
                        try:
                            async with asyncio.timeout(60):  # 60 second timeout for RPC calls including fallback
                                proposals = await client.get_proposals()
                        except asyncio.TimeoutError:
                            logger.error(f"Timeout fetching proposals for {network['name']} (including fallback attempt)")
                            continue
                        
                        for proposal in proposals:
                            current = tracker.get_proposal(proposal.id, network_id=network["name"])
                            await process_cosmos_proposal_alert(
                                proposal, network, current, alert_handler, slack_sender, tracker
                            )
                            
                except Exception as e:
                    logger.error(f"Error processing {network['name']}: {e}")
                    continue
            
            if not continuous:
                break
                
            # Wait for the configured interval before next check
            await asyncio.sleep(check_interval)
            
        except Exception as e:
            logger.error(f"Cosmos monitoring stopped due to error: {e}")
            break

if __name__ == "__main__":
    asyncio.run(monitor_cosmos_proposals(continuous=False)) 