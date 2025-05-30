import logging
from typing import Dict, List
from ...common.alerts.base import BaseAlertHandler, AlertConfig, build_slack_alert_blocks
from .client import TallyProposal

logger = logging.getLogger(__name__)

class TallyAlertHandler(BaseAlertHandler):
    """Handler for Tally-specific alerts."""
    
    def get_alert_types(self) -> List[str]:
        """Return list of alert types supported by this handler."""
        return ["proposal_active", "proposal_update", "proposal_ended"]
    
    def format_alert(self, alert_type: str, data: Dict) -> Dict:
        """Format an alert for Tally proposals."""
        project_name = data["project_name"]
        proposal: TallyProposal = data["proposal"]
        
        # Log alert formatting
        logger.info(f"Formatting {alert_type} alert for {project_name} proposal {proposal.id}")
        
        # Determine alert title based on type
        if alert_type == "proposal_active":
            title = f"{project_name} Onchain Proposal Active"
        elif alert_type == "proposal_update":
            title = f"{project_name} Onchain Proposal Update"
        else:  # proposal_ended
            title = f"{project_name} Onchain Proposal Ended"
        
        # Use shared utility: header for title, context for description (smaller), divider, and actions for button
        description = proposal.title
        button_text = "View Proposal" if proposal.proposal_url else None
        button_url = proposal.proposal_url if proposal.proposal_url else None
        
        message = {
            "unfurl_links": not self.config.disable_link_previews,
            "unfurl_media": False,
            "link_names": True,
            "text": f"*{title}*\n{description}",
            "blocks": build_slack_alert_blocks(title, description, button_text, button_url)
        }
        return message
    
    def should_alert(self, proposal: TallyProposal, previous_status: str = None) -> bool:
        """Determine if an alert should be sent."""
        # Log the decision making process
        logger.info(f"Checking if should alert for proposal {proposal.id} (status: {proposal.status}, previous: {previous_status})")
        
        # Only send new alerts for active proposals
        if not previous_status:
            should_alert = proposal.status == "active"
            logger.info(f"New proposal check: {should_alert}")
            return should_alert
            
        # For existing proposals, only send updates if we've already sent an alert
        if previous_status:
            # Status change to extended
            if previous_status == "active" and proposal.status == "extended":
                logger.info("Status changed to extended")
                return True
                
            # Final status change
            final_statuses = {
                "succeeded", "archived", "canceled", "callexecuted",
                "defeated", "executed", "expired", "queued",
                "pendingexecution", "crosschainexecuted"
            }
            
            if proposal.status in final_statuses:
                logger.info(f"Proposal reached final status: {proposal.status}")
                return True
        
        logger.info("No alert conditions met")
        return False 