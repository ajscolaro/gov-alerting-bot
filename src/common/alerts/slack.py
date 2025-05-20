import aiohttp
from typing import Dict, Optional

from src.common.alerts.base import BaseAlertHandler, AlertConfig


class SlackAlertSender:
    """Handles sending alerts to Slack using a bot token."""
    
    def __init__(self, config: AlertConfig):
        self.config = config
        self.api_base_url = "https://slack.com/api"
        self._channel_id: Optional[str] = None
    
    async def _get_channel_id(self) -> Optional[str]:
        """Get the channel ID from the channel name."""
        if self._channel_id:
            return self._channel_id
            
        headers = {
            "Authorization": f"Bearer {self.config.slack_bot_token}",
            "Content-Type": "application/json"
        }
        
        async with aiohttp.ClientSession(headers=headers) as session:
            # First try to get the channel directly
            async with session.get(
                f"{self.api_base_url}/conversations.info",
                params={"channel": self.config.slack_channel}
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    if result.get("ok"):
                        self._channel_id = result["channel"]["id"]
                        return self._channel_id
            
            # If that fails, try to list all channels and find the matching one
            async with session.get(
                f"{self.api_base_url}/conversations.list",
                params={"types": "public_channel,private_channel"}
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    if result.get("ok"):
                        channel_name = self.config.slack_channel.lstrip("#")
                        for channel in result["channels"]:
                            if channel["name"] == channel_name:
                                self._channel_id = channel["id"]
                                return self._channel_id
        
        return None
    
    async def send_alert(self, alert_handler: BaseAlertHandler, message: Dict) -> Dict:
        """Send an alert to Slack using the bot token.
        
        Returns:
            Dict containing success status and message timestamp if successful:
            {
                "ok": bool,
                "ts": str or None
            }
        """
        # Get channel ID
        channel_id = await self._get_channel_id()
        if not channel_id:
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