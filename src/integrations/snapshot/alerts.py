from typing import Dict, List
from ...common.alerts.base import BaseAlertHandler, AlertConfig, build_slack_alert_blocks
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class SnapshotAlertHandler(BaseAlertHandler):
    """Handler for Snapshot-specific alerts."""
    
    def get_alert_types(self) -> List[str]:
        """Return list of alert types supported by this handler."""
        return ["proposal_active", "proposal_ended", "proposal_deleted", "space_not_detected"]
    
    def format_alert(self, alert_type: str, data: Dict) -> Dict:
        """Format an alert for Snapshot proposals."""
        project_name = data["project_name"]
        
        # Log alert formatting
        logger.info(f"Formatting {alert_type} alert for {project_name}")
        
        # Handle space not detected alert type
        if alert_type == "space_not_detected":
            title = f"Admin Action Required: {project_name} Space Not Detected"
            description = f"The Snapshot space '{data['proposal']['space']}' could not be found. Please verify the space ID in the watchlist."
            button_text = "View Space"
            button_url = data["snapshot_url"]
        else:
            # Handle proposal alerts
            proposal = data["proposal"]
            snapshot_url = data["snapshot_url"]
            
            # Determine alert title based on type
            if alert_type == "proposal_active":
                title = f"{project_name} Snapshot Proposal Active"
                button_text = "View Proposal"
            elif alert_type == "proposal_ended":
                title = f"{project_name} Snapshot Proposal Ended"
                button_text = "View Proposal"
            else:  # proposal_deleted
                title = f"{project_name} Snapshot Proposal Deleted"
                button_text = None
            
            description = proposal["title"]
            button_url = f"{snapshot_url}/proposal/{proposal['id']}" if button_text else None
        
        message = {
            "unfurl_links": not self.config.disable_link_previews,
            "unfurl_media": False,
            "link_names": True,
            "text": f"*{title}*\n{description}",
            "blocks": build_slack_alert_blocks(title, description, button_text, button_url)
        }
        
        # For non-active alerts, add thread context if available
        if alert_type not in ["proposal_active", "space_not_detected"] and "thread_ts" in data:
            message["thread_ts"] = data["thread_ts"]
            message["reply_broadcast"] = True
            logger.info(f"Sending {alert_type} as thread reply with ts: {data['thread_ts']}")
        
        return message
    
    def should_alert(self, proposal: Dict = None, previous_status: str = None, space_id: str = None, alert_type: str = None) -> bool:
        """Determine if an alert should be sent."""
        # Handle space not detected alert
        if alert_type == "space_not_detected":
            logger.info(f"Should send space_not_detected alert")
            return True
            
        # Handle proposal alerts
        if proposal is None:
            return False
            
        # Log the decision making process
        logger.info(f"Checking if should alert for proposal {proposal['id']} (status: {proposal['state']}, previous: {previous_status})")
        
        # Only send new alerts for active proposals
        if not previous_status:
            should_alert = proposal["state"] == "active"
            logger.info(f"New proposal check: {should_alert}")
            return should_alert
            
        # For existing proposals, only send updates if we've already sent an alert
        if previous_status:
            # Status change from active
            if previous_status == "active":
                if proposal["state"] == "closed":
                    logger.info("Proposal ended")
                    return True
                elif proposal["state"] == "deleted":
                    logger.info("Proposal deleted")
                    return True
        
        logger.info("No alert conditions met")
        return False 