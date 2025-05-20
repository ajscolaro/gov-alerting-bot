from typing import Dict, List
from src.common.alerts.base import BaseAlertHandler, AlertConfig
from src.integrations.tally.client import TallyProposal

class TallyAlertHandler(BaseAlertHandler):
    """Handler for Tally-specific alerts."""
    
    def get_alert_types(self) -> List[str]:
        """Return list of alert types supported by this handler."""
        return ["proposal_active", "proposal_update", "proposal_ended"]
    
    def format_alert(self, alert_type: str, data: Dict) -> Dict:
        """Format an alert for Tally proposals."""
        project_name = data["project_name"]
        proposal: TallyProposal = data["proposal"]
        
        # Determine alert title based on type
        if alert_type == "proposal_active":
            title = f"*{project_name} Proposal Active*"
        elif alert_type == "proposal_update":
            title = f"*{project_name} Proposal Update*"
        else:  # proposal_ended
            title = f"*{project_name} Proposal Ended*"
        
        # Base message structure with standardized format
        message = {
            "unfurl_links": not self.config.disable_link_previews,
            "unfurl_media": False,
            "link_names": True,
            "text": f"{title}\n{proposal.title}",  # For notifications
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"{title}\n{proposal.title}"
                    }
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "View on Tally",
                                "emoji": True
                            },
                            "url": proposal.proposal_url
                        }
                    ]
                }
            ]
        }
        
        return message
    
    def should_alert(self, proposal: TallyProposal, previous_status: str = None) -> bool:
        """Determine if an alert should be sent."""
        # Only send new alerts for active proposals
        if not previous_status:
            return proposal.status == "active"
            
        # For existing proposals, only send updates if we've already sent an alert
        if previous_status:
            # Status change to extended
            if previous_status == "active" and proposal.status == "extended":
                return True
                
            # Final status change
            final_statuses = {
                "succeeded", "archived", "canceled", "callexecuted",
                "defeated", "executed", "expired", "queued",
                "pendingexecution", "crosschainexecuted"
            }
            
            if proposal.status in final_statuses:
                return True
        
        return False 