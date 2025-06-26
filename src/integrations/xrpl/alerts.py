from typing import Dict, List, Optional
from ...common.alerts.base import BaseAlertHandler, AlertConfig, build_slack_alert_blocks
from .client import XRPLAmendment

class XRPLAlertHandler(BaseAlertHandler):
    """Handler for XRPL-specific alerts."""
    
    def get_alert_types(self) -> List[str]:
        """Return list of alert types supported by this handler."""
        return ["amendment_active", "amendment_ended"]
    
    def format_alert(self, alert_type: str, data: dict) -> dict:
        """Format alert message for Slack."""
        amendment = data["amendment"]
        network_name = data.get("network_name", "XRP Ledger")
        
        # Determine title based on alert type
        if alert_type == "amendment_active":
            title = f"{network_name} Amendment Active"
        else:  # amendment_ended
            title = f"{network_name} Amendment Enabled"
        
        # Format amendment description - just the name
        amendment_title = amendment.name
        
        # Add enabled date for ended amendments
        if alert_type == "amendment_ended" and amendment.enabled_on:
            # Format the enabled_on timestamp
            try:
                from datetime import datetime
                enabled_date = datetime.fromisoformat(amendment.enabled_on.replace('Z', '+00:00'))
                formatted_date = enabled_date.strftime("%Y-%m-%d %H:%M UTC")
                amendment_title += f" - Enabled on {formatted_date}"
            except:
                amendment_title += f" - Enabled on {amendment.enabled_on}"
        
        button_text = "View Amendment"
        button_url = data.get("amendment_url", "")
        
        # Use shared utility: header for title, context for description (smaller), divider, and actions for button
        message = {
            "text": f"*{title}*\n{amendment_title}",
            "blocks": build_slack_alert_blocks(title, amendment_title, button_text, button_url)
        }
        return message
    
    def should_alert(self, amendment: XRPLAmendment, previous_enabled: bool = None) -> bool:
        """Determine if an alert should be sent."""
        import logging
        logger = logging.getLogger(__name__)
        
        # Log the decision making process
        logger.info(f"Checking if should alert for amendment {amendment.amendment_id} (enabled: {amendment.enabled}, previous: {previous_enabled})")
        
        # For new amendments, only alert when they're active (not enabled but supported)
        if previous_enabled is None:
            should_alert = amendment.is_active()
            logger.info(f"New amendment check: {should_alert}")
            return should_alert
            
        # For existing amendments, alert when they become enabled
        if not previous_enabled and amendment.enabled and amendment.enabled_on:
            logger.info(f"Amendment ended check: True (became enabled)")
            return True
        
        logger.info(f"No alert conditions met")
        return False 