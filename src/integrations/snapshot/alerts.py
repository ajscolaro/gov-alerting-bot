from typing import Dict, List
from ...common.alerts.base import BaseAlertHandler, AlertConfig
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class SnapshotAlertHandler(BaseAlertHandler):
    """Handler for Snapshot-specific alerts."""
    
    def get_alert_types(self) -> List[str]:
        """Return list of alert types supported by this handler."""
        return ["proposal_active", "proposal_ended", "proposal_deleted"]
    
    def format_alert(self, alert_type: str, data: Dict) -> Dict:
        """Format an alert for Snapshot proposals."""
        project_name = data["project_name"]
        proposal = data["proposal"]
        snapshot_url = data["snapshot_url"]
        
        # Log alert formatting
        logger.info(f"Formatting {alert_type} alert for {project_name} proposal {proposal['id']}")
        
        # Determine alert title based on type
        if alert_type == "proposal_active":
            title = f"*{project_name} Offchain Proposal Active*"
        elif alert_type == "proposal_ended":
            title = f"*{project_name} Offchain Proposal Ended*"
        else:  # proposal_deleted
            title = f"*{project_name} Offchain Proposal Deleted*"
        
        # Base message structure with standardized format
        message = {
            "unfurl_links": not self.config.disable_link_previews,
            "unfurl_media": False,
            "link_names": True,
            "text": f"{title}\n{proposal['title']}",  # For notifications
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
                        "text": proposal["title"]
                    }
                }
            ]
        }
        
        # Add button for active and ended proposals
        if alert_type != "proposal_deleted":
            message["blocks"].append({
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "View Proposal" if alert_type == "proposal_active" else "View Results",
                            "emoji": True
                        },
                        "url": f"{snapshot_url}/proposal/{proposal['id']}"
                    }
                ]
            })
        
        # For non-active alerts, add thread context if available
        if alert_type != "proposal_active" and "thread_ts" in data:
            message["thread_ts"] = data["thread_ts"]
            message["reply_broadcast"] = True
            logger.info(f"Sending {alert_type} as thread reply with ts: {data['thread_ts']}")
        
        return message
    
    def should_alert(self, proposal: Dict, previous_status: str = None) -> bool:
        """Determine if an alert should be sent."""
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