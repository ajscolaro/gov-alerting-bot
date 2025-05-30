from typing import Dict, List, Optional
from ...common.alerts.base import BaseAlertHandler, AlertConfig, build_slack_alert_blocks
from .client import CosmosProposal

class CosmosAlertHandler(BaseAlertHandler):
    """Handler for Cosmos-specific alerts."""
    
    def get_alert_types(self) -> List[str]:
        """Return list of alert types supported by this handler."""
        return ["proposal_voting", "proposal_ended"]
    
    def format_alert(self, alert_type: str, data: dict) -> dict:
        """Format alert message for Slack."""
        proposal = data["proposal"]
        network_name = data.get("network_name", "Cosmos")
        
        # Determine title based on alert type
        if alert_type == "proposal_voting":
            title = f"{network_name} Onchain Proposal Active"
        else:  # proposal_ended
            title = f"{network_name} Onchain Proposal Ended"
        
        proposal_title = f"Proposal {proposal.id}"
        button_text = "View Proposal" if proposal.proposal_url else None
        button_url = proposal.proposal_url if proposal.proposal_url else None
        
        # Use shared utility: header for title, context for description (smaller), divider, and actions for button
        message = {
            "text": f"*{title}*\n{proposal_title}",
            "blocks": build_slack_alert_blocks(title, proposal_title, button_text, button_url)
        }
        return message
    
    def should_alert(self, proposal: CosmosProposal, previous_status: str = None) -> bool:
        """Determine if an alert should be sent."""
        import logging
        logger = logging.getLogger(__name__)
        
        # Log the decision making process
        logger.info(f"Checking if should alert for proposal {proposal.id} (status: {proposal.status}, previous: {previous_status})")
        
        # For new proposals, only alert when they're in voting period
        if not previous_status:
            should_alert = proposal.status == "PROPOSAL_STATUS_VOTING_PERIOD"
            logger.info(f"New proposal check: {should_alert}")
            return should_alert
            
        # For existing proposals, alert when voting ends
        if previous_status == "PROPOSAL_STATUS_VOTING_PERIOD" and proposal.status != "PROPOSAL_STATUS_VOTING_PERIOD":
            logger.info(f"Voting ended check: True (status changed from voting period to {proposal.status})")
            return True
        
        logger.info(f"No alert conditions met")
        return False