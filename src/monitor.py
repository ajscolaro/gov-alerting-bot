import asyncio
import json
import logging
import os
from typing import Dict, Optional, List
from datetime import datetime, timedelta
from pathlib import Path

from common.alerts.slack import SlackAlertSender
from common.alerts.base import AlertConfig
from integrations.tally.client import TallyClient, TallyProposal
from integrations.tally.alerts import TallyAlertHandler
from integrations.cosmos.client import CosmosClient, CosmosProposal
from integrations.cosmos.alerts import CosmosAlertHandler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class PersistentProposalTracker:
    """Tracks proposals and their status changes with file-based persistence."""
    
    def __init__(self, state_file: str = "data/proposal_state.json"):
        self.state_file = state_file
        self.proposals: Dict[str, Dict[str, Dict]] = self._load_state()
        # Initialize framework sections if they don't exist
        if "tally" not in self.proposals:
            self.proposals["tally"] = {}
        if "cosmos" not in self.proposals:
            self.proposals["cosmos"] = {}
        logger.info(f"Loaded state from {state_file}: {len(self.get_all_proposals())} proposals")
    
    def _load_state(self) -> Dict[str, Dict[str, Dict]]:
        """Load proposal state from file."""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, "r") as f:
                    return json.load(f)
            return {"tally": {}, "cosmos": {}}
        except Exception as e:
            logger.error(f"Error loading proposal state: {e}")
            return {"tally": {}, "cosmos": {}}
    
    def _save_state(self):
        """Save current proposal state to file."""
        try:
            os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
            with open(self.state_file, "w") as f:
                json.dump(self.proposals, f, indent=2)
            logger.info(f"Saved state to {self.state_file}")
        except Exception as e:
            logger.error(f"Error saving proposal state: {e}")
    
    def get_proposal(self, proposal_id: str, framework: str = "tally") -> Optional[Dict]:
        """Get proposal by ID and framework type."""
        return self.proposals.get(framework, {}).get(proposal_id)
    
    def update_proposal(self, proposal_id: str, status: str, thread_ts: Optional[str] = None, 
                       alerted: bool = False, framework: str = "tally"):
        """Update proposal with framework type."""
        if framework not in self.proposals:
            self.proposals[framework] = {}
            
        if proposal_id in self.proposals[framework]:
            self.proposals[framework][proposal_id]["status"] = status
            if thread_ts:
                self.proposals[framework][proposal_id]["thread_ts"] = thread_ts
            if alerted:
                self.proposals[framework][proposal_id]["alerted"] = True
        else:
            self.proposals[framework][proposal_id] = {
                "status": status,
                "thread_ts": thread_ts,
                "alerted": alerted
            }
        self._save_state()
    
    def remove_proposal(self, proposal_id: str, framework: str = "tally"):
        """Remove proposal by ID and framework type."""
        if framework in self.proposals and proposal_id in self.proposals[framework]:
            del self.proposals[framework][proposal_id]
            self._save_state()
    
    def get_tracked_proposals_count(self, framework: str = None) -> int:
        """Get the number of currently tracked proposals, optionally by framework."""
        if framework:
            return len(self.proposals.get(framework, {}))
        else:
            return len(self.get_all_proposals())
            
    def get_all_proposals(self) -> Dict[str, Dict]:
        """Get all proposals across all frameworks."""
        all_proposals = {}
        for framework, proposals in self.proposals.items():
            for prop_id, prop_data in proposals.items():
                all_proposals[f"{framework}:{prop_id}"] = prop_data
        return all_proposals

async def load_watchlist():
    """Load the watchlist from file."""
    try:
        with open("data/watchlist.json", "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading watchlist: {e}")
        return {"tally": [], "cosmos": []}

async def monitor_tally_proposals(
    slack_sender: SlackAlertSender,
    alert_handler: TallyAlertHandler,
    tracker: PersistentProposalTracker
):
    """Monitor Tally proposals and send alerts."""
    watchlist = await load_watchlist()
    tally_projects = watchlist.get("tally", [])
    
    if not tally_projects:
        logger.warning("No Tally projects found in watchlist")
        return
    
    async with TallyClient() as client:
        while True:
            try:
                for project in tally_projects:
                    logger.info(f"Checking proposals for {project['name']}")
                    
                    try:
                        tally_metadata = project["metadata"]
                        proposals = await client.get_proposals(
                            tally_metadata["governor_address"],
                            tally_metadata["chain_id"]
                        )
                        
                        for proposal in proposals:
                            # Construct proposal URL
                            proposal.proposal_url = f"{tally_metadata['tally_url']}/proposal/{proposal.id}"
                            
                            current = tracker.get_proposal(proposal.id)
                            previous_status = current["status"] if current else None
                            
                            if alert_handler.should_alert(proposal, previous_status):
                                # Determine alert type
                                if not previous_status:
                                    alert_type = "proposal_active"
                                elif previous_status == "active" and proposal.status == "extended":
                                    alert_type = "proposal_update"
                                else:
                                    alert_type = "proposal_ended"
                                
                                logger.info(f"Sending {alert_type} alert for {project['name']} proposal {proposal.id}")
                                
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
                                        message["reply_broadcast"] = True  # Ensure replies are visible in channel
                                        logger.info(f"Sending {alert_type} as thread reply with ts: {current['thread_ts']}")
                                    else:
                                        # Add warning about missing thread context
                                        message["text"] = f"⚠️ Unable to find original message context. {message['text']}"
                                        logger.warning(f"No thread context found for proposal {proposal.id}")
                                
                                # Send the alert
                                result = await slack_sender.send_alert(alert_handler, message)
                                
                                if result["ok"]:
                                    if alert_type == "proposal_active":
                                        # Store thread timestamp for future replies
                                        tracker.update_proposal(proposal.id, proposal.status, result["ts"], True)
                                        logger.info(f"Stored thread timestamp for new proposal: {result['ts']}")
                                    elif alert_type == "proposal_ended":
                                        # Check if this is a final status
                                        final_statuses = {
                                            "succeeded", "archived", "canceled", "callexecuted",
                                            "defeated", "executed", "expired", "queued",
                                            "pendingexecution", "crosschainexecuted"
                                        }
                                        
                                        if proposal.status.lower() in final_statuses:
                                            # Remove ended proposals from tracking
                                            tracker.remove_proposal(proposal.id)
                                            logger.info(f"Removed ended proposal from tracking: {proposal.id}")
                                        else:
                                            # Update status without changing thread_ts
                                            tracker.update_proposal(proposal.id, proposal.status, current.get("thread_ts"), True)
                                            logger.info(f"Updated proposal status while maintaining thread context: {proposal.status}")
                                    else:
                                        # Update status without changing thread_ts
                                        tracker.update_proposal(proposal.id, proposal.status, current.get("thread_ts"), True)
                                        logger.info(f"Updated proposal status while maintaining thread context: {proposal.status}")
                                else:
                                    # Update status without changing thread_ts
                                    tracker.update_proposal(proposal.id, proposal.status, current.get("thread_ts"))
                                    logger.warning(f"Failed to send alert, updated status only: {proposal.status}")
                            elif current and current.get("status") != proposal.status:
                                # Just update the status if alert is not needed but status changed
                                tracker.update_proposal(proposal.id, proposal.status, current.get("thread_ts"))
                                logger.info(f"Updated proposal status without alert: {proposal.status}")
                            
                    except Exception as e:
                        logger.error(f"Error processing {project['name']}: {e}")
                        continue
                
                # Log number of tracked proposals
                logger.info(f"Currently tracking {tracker.get_tracked_proposals_count()} proposals")
                
                # Wait before next check
                check_interval = int(os.getenv("CHECK_INTERVAL", "60").split("#")[0].strip())
                await asyncio.sleep(check_interval)
                
            except Exception as e:
                logger.error(f"Error monitoring proposals: {e}")
                await asyncio.sleep(60)  # Wait before retrying

async def monitor_cosmos_proposals(
    slack_sender: SlackAlertSender,
    alert_handler: CosmosAlertHandler,
    tracker: PersistentProposalTracker
):
    """Monitor Cosmos proposals and send alerts."""
    watchlist = await load_watchlist()
    cosmos_networks = watchlist.get("cosmos", [])
    
    if not cosmos_networks:
        logger.warning("No Cosmos networks found in watchlist")
        return
    
    # Define final statuses for Cosmos proposals
    final_statuses = {
        "PROPOSAL_STATUS_PASSED",
        "PROPOSAL_STATUS_REJECTED",
        "PROPOSAL_STATUS_FAILED"
    }
    
    while True:
        try:
            for network in cosmos_networks:
                logger.info(f"Checking active proposals for {network['name']}")
                
                try:
                    metadata = network["metadata"]
                    async with CosmosClient(
                        base_url=metadata["rpc_url"],
                        chain_id=metadata["chain_id"],
                        explorer_url=metadata.get("explorer_url"),
                        explorer_type=metadata.get("explorer_type", "mintscan")
                    ) as client:
                        # Get active and ended proposals
                        proposals = await client.get_proposals()
                        
                        for proposal in proposals:
                            current = tracker.get_proposal(proposal.id, framework="cosmos")
                            previous_status = current["status"] if current else None
                            
                            # Skip if we've already alerted about this proposal and it hasn't changed status
                            if current and current.get("alerted", False) and current.get("status") == proposal.status:
                                logger.info(f"Skipping already alerted proposal {proposal.id} with unchanged status")
                                continue
                            
                            if alert_handler.should_alert(proposal, previous_status):
                                # Determine alert type
                                if not previous_status:
                                    alert_type = "proposal_voting"
                                else:
                                    alert_type = "proposal_ended"
                                
                                logger.info(f"Sending {alert_type} alert for {network['name']} proposal {proposal.id}")
                                
                                # Prepare alert data
                                alert_data = {
                                    "network_name": network["name"],
                                    "proposal": proposal,
                                    "explorer_type": metadata.get("explorer_type", "mintscan"),
                                    "explorer_name": metadata.get("explorer_name", "Mintscan")
                                }
                                
                                # Format and send alert
                                message = alert_handler.format_alert(alert_type, alert_data)
                                
                                # Handle thread context for replies
                                if alert_type != "proposal_voting":
                                    if current and current.get("thread_ts"):
                                        message["thread_ts"] = current["thread_ts"]
                                        message["reply_broadcast"] = True  # Ensure replies are visible in channel
                                        logger.info(f"Sending {alert_type} as thread reply with ts: {current['thread_ts']}")
                                    else:
                                        # Add warning about missing thread context
                                        message["text"] = f"⚠️ Unable to find original message context. {message['text']}"
                                        logger.warning(f"No thread context found for proposal {proposal.id}")
                                
                                # Send the alert
                                result = await slack_sender.send_alert(alert_handler, message)
                                
                                if result["ok"]:
                                    if alert_type == "proposal_voting":
                                        # Store thread timestamp for future replies
                                        tracker.update_proposal(
                                            proposal.id,
                                            proposal.status,
                                            result["ts"],
                                            True,  # Mark as alerted
                                            framework="cosmos"
                                        )
                                        logger.info(f"Stored thread timestamp for new proposal: {result['ts']}")
                                    elif alert_type == "proposal_ended":
                                        # Check if this is a final status
                                        if proposal.status in final_statuses:
                                            # Remove ended proposals from tracking
                                            tracker.remove_proposal(proposal.id, framework="cosmos")
                                            logger.info(f"Removed ended proposal from tracking: {proposal.id}")
                                        else:
                                            # Update status without changing thread_ts
                                            tracker.update_proposal(
                                                proposal.id,
                                                proposal.status,
                                                current.get("thread_ts"),
                                                True,  # Mark as alerted
                                                framework="cosmos"
                                            )
                                            logger.info(f"Updated proposal status while maintaining thread context: {proposal.status}")
                                else:
                                    # Update status without changing thread_ts if alert fails
                                    tracker.update_proposal(
                                        proposal.id,
                                        proposal.status,
                                        current.get("thread_ts") if current else None,
                                        current.get("alerted", False),  # Keep existing alerted state
                                        framework="cosmos"
                                    )
                                    logger.warning(f"Failed to send alert, updated status only: {proposal.status}")
                            elif current and current.get("status") != proposal.status:
                                # Just update the status if alert is not needed but status changed
                                tracker.update_proposal(
                                    proposal.id,
                                    proposal.status,
                                    current.get("thread_ts"),
                                    current.get("alerted", False),  # Keep existing alerted state
                                    framework="cosmos"
                                )
                                logger.info(f"Updated proposal status without alert: {proposal.status}")
                
                except Exception as e:
                    logger.error(f"Error monitoring {network['name']}: {e}")
                    continue
            
            # Wait before next check
            await asyncio.sleep(300)  # 5 minutes
            
        except Exception as e:
            logger.error(f"Error in monitor loop: {e}")
            await asyncio.sleep(60)  # Wait a minute before retrying

async def process_cosmos_proposal_alert(
    proposal, 
    network, 
    current, 
    alert_handler, 
    slack_sender, 
    tracker
):
    """Process alerts for a Cosmos proposal."""
    network_id = network["platform_specific_id"]
    
    # Determine alert type based on status change
    if not current or current.get("status") != "PROPOSAL_STATUS_VOTING_PERIOD":
        alert_type = "proposal_voting"
        logger.info(f"New voting proposal detected: {proposal.id}")
    else:
        alert_type = "proposal_ended"
        logger.info(f"Proposal status changed from voting to {proposal.status}: {proposal.id}")
    
    logger.info(f"Sending {alert_type} alert for {network['name']} proposal {proposal.id}")
    
    # Prepare alert data
    alert_data = {
        "network_name": network["name"],
        "proposal": proposal
    }
    
    # Format and send alert
    message = alert_handler.format_alert(alert_type, alert_data)
    
    # Handle thread context for replies
    if alert_type != "proposal_voting":
        if current and current.get("thread_ts"):
            message["thread_ts"] = current["thread_ts"]
            message["reply_broadcast"] = True  # Ensure replies are visible in channel
            logger.info(f"Sending {alert_type} as thread reply with ts: {current['thread_ts']}")
        else:
            # Add warning about missing thread context
            message["text"] = f"⚠️ Unable to find original message context. {message['text']}"
            logger.warning(f"No thread context found for proposal {proposal.id}")
    
    # Send the alert
    result = await slack_sender.send_alert(alert_handler, message)
    
    if result["ok"]:
        if alert_type == "proposal_voting":
            # Store thread timestamp for future replies
            tracker.update_proposal(
                f"{network_id}:{proposal.id}", 
                proposal.status,
                result["ts"],
                True,
                framework="cosmos"
            )
            logger.info(f"Stored thread timestamp for new proposal: {result['ts']}")
        elif alert_type == "proposal_ended":
            # Only remove the proposal after sending the ended alert
            tracker.remove_proposal(f"{network_id}:{proposal.id}", "cosmos")
            logger.info(f"Removed ended proposal from tracking: {proposal.id}")
    else:
        # Update status without changing thread_ts if alert fails
        tracker.update_proposal(
            f"{network_id}:{proposal.id}", 
            proposal.status,
            current.get("thread_ts") if current else None,
            current.get("alerted", False),
            framework="cosmos"
        )
        logger.warning(f"Failed to send alert, updated status only: {proposal.status}")

async def run_all_monitors():
    """Run all monitoring services."""
    # Load configuration from environment variables
    config = AlertConfig(
        slack_bot_token=os.getenv("SLACK_BOT_TOKEN"),
        slack_channel=os.getenv("SLACK_CHANNEL"),
        disable_link_previews=True,
        enabled_alert_types=["proposal_active", "proposal_update", "proposal_ended",
                             "proposal_voting", "proposal_ended"]
    )
    
    if not config.slack_bot_token or not config.slack_channel:
        logger.error("Missing required environment variables: SLACK_BOT_TOKEN and/or SLACK_CHANNEL")
        return
    
    # Initialize components
    slack_sender = SlackAlertSender(config)
    tally_handler = TallyAlertHandler(config)
    cosmos_handler = CosmosAlertHandler(config)
    
    # Use a single tracker for all proposal types
    tracker = PersistentProposalTracker("data/proposal_state.json")
    
    # Run both monitoring tasks in parallel
    await asyncio.gather(
        monitor_tally_proposals(slack_sender, tally_handler, tracker),
        monitor_cosmos_proposals(slack_sender, cosmos_handler, tracker)
    )

async def main():
    """Main entry point."""
    # Ensure data directories exist
    os.makedirs("data", exist_ok=True)
    
    # Run all monitors
    await run_all_monitors()

if __name__ == "__main__":
    asyncio.run(main()) 