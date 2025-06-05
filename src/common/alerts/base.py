from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, Optional, List
from pydantic import BaseModel

from ..models import Proposal, WatchlistItem


class AlertType(str, Enum):
    """Base alert types that might be common across platforms."""
    NEW_PROPOSAL = "new_proposal"
    STATUS_CHANGE = "status_change"
    VOTING_STARTED = "voting_started"
    VOTING_ENDED = "voting_ended"


class AlertConfig(BaseModel):
    """Base configuration for alerts."""
    slack_bot_token: str
    app_slack_channel: str  # Channel for app alerts
    net_slack_channel: str  # Channel for network alerts
    test_slack_channel: str  # Channel for test alerts
    slack_channel: Optional[str] = None  # For backward compatibility
    disable_link_previews: bool = True
    enabled_alert_types: List[str] = []  # Platform-specific alert types
    is_test_mode: bool = False  # Whether to use test channel

    def get_channel_for_label(self, intel_label: Optional[str]) -> str:
        """Get the appropriate channel based on intel_label and test mode.
        
        Args:
            intel_label: The intel_label from the watchlist item ("app" or "net")
            
        Returns:
            The appropriate channel ID based on intel_label and test mode.
            Raises ValueError if intel_label is invalid or channels are not configured.
        """
        # In test mode, always use the test channel
        if self.is_test_mode:
            if not self.test_slack_channel:
                raise ValueError("test_slack_channel is required for test mode")
            return self.test_slack_channel
            
        if not intel_label:
            raise ValueError("intel_label is required for channel selection")
            
        if intel_label == "app":
            if not self.app_slack_channel:
                raise ValueError("app_slack_channel is required for app alerts")
            return self.app_slack_channel
            
        if intel_label == "net":
            if not self.net_slack_channel:
                raise ValueError("net_slack_channel is required for net alerts")
            return self.net_slack_channel
            
        raise ValueError(f"Invalid intel_label: {intel_label}. Must be 'app' or 'net'")


class BaseAlertHandler(ABC):
    """Base class for alert handlers."""
    
    def __init__(self, config: AlertConfig):
        self.config = config
    
    @abstractmethod
    def get_alert_types(self) -> List[str]:
        """Return list of alert types supported by this handler."""
        pass
    
    @abstractmethod
    def format_alert(self, alert_type: str, data: Dict) -> Dict:
        """Format an alert for the specific platform and alert type."""
        pass
    
    def get_common_slack_format(self) -> Dict:
        """Get common Slack message formatting."""
        return {
            "unfurl_links": not self.config.disable_link_previews,
            "unfurl_media": False,
            "link_names": True
        }
    
    def is_alert_type_enabled(self, alert_type: str) -> bool:
        """Check if an alert type is enabled in the configuration."""
        return alert_type in self.config.enabled_alert_types

    def should_alert(self, proposal: Proposal, previous_status: Optional[str] = None) -> bool:
        """Determine if an alert should be sent based on configuration."""
        if self.config.alert_on_new_proposals and not previous_status:
            return True
        if self.config.alert_on_status_changes and previous_status and previous_status != proposal.status:
            return True
        return False 

def build_slack_alert_blocks(title: str, description: str, button_text: str = None, button_url: str = None) -> list:
    """
    Build Slack blocks for alerts with a stylish, consistent format:
    - Title as a header (prominent)
    - Description/content as a context block (smaller, lighter)
    - Divider
    - Button (if provided)
    """
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": title,
                "emoji": True
            }
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": description
                }
            ]
        },
        {"type": "divider"}
    ]
    if button_text and button_url:
        blocks.append({
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": button_text,
                        "emoji": True
                    },
                    "url": button_url
                }
            ]
        })
    return blocks 