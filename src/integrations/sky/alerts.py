import logging
from typing import Dict, List
from ...common.alerts.base import BaseAlertHandler, AlertConfig, build_slack_alert_blocks
from .client import SkyProposal

logger = logging.getLogger(__name__)

class SkyAlertHandler(BaseAlertHandler):
    """Handler for Sky-specific alerts."""
    
    def get_alert_types(self) -> List[str]:
        """Return list of alert types supported by this handler."""
        return ["proposal_active", "proposal_update", "proposal_ended"]
    
    def format_alert(self, alert_type: str, data: Dict) -> Dict:
        """Format an alert for Sky proposals."""
        project_name = data["project_name"]
        proposal: SkyProposal = data["proposal"]
        
        # Log alert formatting
        logger.info(f"Formatting {alert_type} alert for {project_name} {proposal.type} {proposal.id}")
        
        # Determine alert title based on type and proposal type
        if alert_type == "proposal_active":
            title = f"{project_name} {proposal.type.title()} Vote Active" if proposal.type == "executive" else f"{project_name} {proposal.type.title()} Active"
        elif alert_type == "proposal_update":
            title = f"{project_name} {proposal.type.title()} Vote Update" if proposal.type == "executive" else f"{project_name} {proposal.type.title()} Update"
        else:  # proposal_ended
            title = f"{project_name} {proposal.type.title()} Vote Executed" if proposal.type == "executive" else f"{project_name} {proposal.type.title()} Ended"
        
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

        # For non-active alerts, ensure thread replies are broadcast
        if alert_type != "proposal_active" and "thread_ts" in data:
            message["reply_broadcast"] = True
            logger.info(f"Sending {alert_type} as thread reply with broadcast enabled")

        return message
    
    def should_alert(self, proposal: SkyProposal, previous_status: str = None) -> bool:
        """Determine if an alert should be sent."""
        # Log the decision making process
        logger.info(f"Checking if should alert for {proposal.type} {proposal.id} (status: {proposal.status}, previous: {previous_status})")
        
        # For new proposals
        if not previous_status:
            should_alert = proposal.status == "active"
            logger.info(f"New proposal check: {should_alert}")
            return should_alert
            
        # For existing proposals
        if previous_status:
            # For polls - only alert on active and ended states
            if proposal.type == "poll":
                if previous_status == "active" and proposal.status == "ended":
                    logger.info("Poll ended")
                    return True
            
            # For executive votes - alert on passed and executed states
            else:  # executive vote
                # Alert when an active vote passes (as an update)
                if previous_status == "active" and proposal.status == "passed":
                    logger.info("Executive vote passed - sending update alert")
                    return True
                
                # Alert when a passed vote is executed
                if previous_status == "passed" and proposal.status == "executed":
                    logger.info("Executive vote executed")
                    return True
        
        logger.info("No alert conditions met")
        return False 