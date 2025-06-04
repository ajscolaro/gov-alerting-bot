import logging
import os
import aiohttp
from typing import Dict, Optional

from .base import BaseAlertHandler, AlertConfig

logger = logging.getLogger(__name__)


class SlackAlertSender:
    """Handles sending alerts to Slack using a bot token."""
    
    def __init__(self, config: AlertConfig):
        self.config = config
        self.api_base_url = "https://slack.com/api"
        self._channel_ids: Dict[str, str] = {}  # Cache channel IDs by channel name
    
    async def _get_channel_id(self, channel_name: str) -> Optional[str]:
        """Get the channel ID from the channel name."""
        if channel_name in self._channel_ids:
            return self._channel_ids[channel_name]
            
        headers = {
            "Authorization": f"Bearer {self.config.slack_bot_token}",
            "Content-Type": "application/json"
        }
        
        async with aiohttp.ClientSession(headers=headers) as session:
            # First try to get the channel directly
            async with session.get(
                f"{self.api_base_url}/conversations.info",
                params={"channel": channel_name}
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    if result.get("ok"):
                        self._channel_ids[channel_name] = result["channel"]["id"]
                        return self._channel_ids[channel_name]
            
            # If that fails, try to list all channels and find the matching one
            async with session.get(
                f"{self.api_base_url}/conversations.list",
                params={"types": "public_channel,private_channel"}
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    if result.get("ok"):
                        channel_name_clean = channel_name.lstrip("#")
                        for channel in result["channels"]:
                            if channel["name"] == channel_name_clean:
                                self._channel_ids[channel_name] = channel["id"]
                                return self._channel_ids[channel_name]
        
        return None
    
    async def send_alert(self, alert_handler: BaseAlertHandler, message: Dict, intel_label: Optional[str] = None) -> Dict:
        """Send an alert to Slack using the bot token.
        
        Args:
            alert_handler: The alert handler instance
            message: The message to send
            intel_label: Optional intel_label to determine which channel to use
            
        Returns:
            Dict containing success status and message timestamp if successful:
            {
                "ok": bool,
                "ts": str or None
            }
        """
        # Get appropriate channel based on intel_label
        channel_name = self.config.get_channel_for_label(intel_label)
        
        # Get channel ID
        channel_id = await self._get_channel_id(channel_name)
        if not channel_id:
            logger.error(f"Failed to get channel ID for {channel_name}")
            return {"ok": False, "ts": None}
        
        # Merge common formatting with platform-specific message
        formatted_message = {
            **alert_handler.get_common_slack_format(),
            **message,
            "channel": channel_id
        }
        
        headers = {
            "Authorization": f"Bearer {self.config.slack_bot_token}",
            "Content-Type": "application/json"
        }
        
        async with aiohttp.ClientSession(headers=headers) as session:
            # If this is a thread reply, send it with reply_broadcast=True
            if "thread_ts" in formatted_message:
                formatted_message["reply_broadcast"] = True
                
            async with session.post(
                f"{self.api_base_url}/chat.postMessage",
                json=formatted_message
            ) as response:
                if response.status != 200:
                    return {"ok": False, "ts": None}
                
                result = await response.json()
                return {
                    "ok": result.get("ok", False),
                    "ts": result.get("ts") if result.get("ok") else None
                } 