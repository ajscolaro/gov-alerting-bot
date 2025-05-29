from typing import Dict, List, Optional
from ...common.alerts.base import BaseAlertHandler, AlertConfig
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
            title = f"*{network_name} Onchain Proposal Active*"
        else:  # proposal_ended
            title = f"*{network_name} Onchain Proposal Ended*"
        
        # Proposal "title" is just the ID for Cosmos
        proposal_title = f"Proposal {proposal.id}"
        
        # Get explorer type and name from metadata if available
        explorer_type = data.get("explorer_type", "mintscan")
        explorer_name = data.get("explorer_name", "Mintscan")
        
        # Standardized message format with larger title
        message = {
            "text": f"{title}\n{proposal_title}",  # For notifications
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": title.replace("*", ""),  # Remove markdown as header is already prominent
                        "emoji": True
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": proposal_title
                    }
                }
            ]
        }
        
        # Only add button if we have a valid proposal URL
        if proposal.proposal_url:
            message["blocks"].append({
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "View Proposal",
                            "emoji": True
                        },
                        "url": proposal.proposal_url
                    }
                ]
            })
        
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