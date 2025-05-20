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
    slack_channel: str
    disable_link_previews: bool = True
    enabled_alert_types: List[str] = []  # Platform-specific alert types


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