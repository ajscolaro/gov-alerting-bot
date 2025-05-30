import aiohttp
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)

@dataclass
class SkyProposal:
    """Represents a Sky governance proposal (either Poll or Executive Vote)."""
    id: str
    title: str
    description: str
    status: str
    start_time: datetime
    end_time: Optional[datetime]
    proposal_url: Optional[str]
    type: str  # "poll" or "executive"
    support: Optional[float]  # For executive votes, the current support percentage

class SkyClient:
    """Client for interacting with the Sky governance API."""
    
    def __init__(self, base_url: str = "https://vote.sky.money"):
        self.base_url = base_url
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def get_polls(self) -> List[Dict]:
        """Get all active polls."""
        if not self.session:
            raise RuntimeError("Client must be used as an async context manager")
            
        try:
            # First get active poll IDs
            async with self.session.get(f"{self.base_url}/api/polling/active-poll-ids") as response:
                if response.status == 404:
                    logger.info("No active polls found")
                    return []
                response.raise_for_status()
                poll_ids = await response.json()
                
            # Then get details for each poll
            polls = []
            for poll_id in poll_ids:
                async with self.session.get(f"{self.base_url}/api/polling/{poll_id}") as response:
                    if response.status == 404:
                        continue
                    response.raise_for_status()
                    poll_data = await response.json()
                    polls.append(poll_data)
                    
            return polls
        except Exception as e:
            logger.error(f"Error fetching polls: {e}")
            return []
    
    async def get_executive_votes(self) -> List[Dict]:
        """Get all active executive votes."""
        if not self.session:
            raise RuntimeError("Client must be used as an async context manager")
            
        try:
            async with self.session.get(f"{self.base_url}/api/executive") as response:
                if response.status == 404:
                    logger.info("No executive votes found")
                    return []
                response.raise_for_status()
                data = await response.json()
                if isinstance(data, list):
                    return data
                return data.get("executive_votes", [])
        except Exception as e:
            logger.error(f"Error fetching executive votes: {e}")
            return []
    
    async def get_proposal(self, proposal_id: str, proposal_type: str) -> Optional[Dict]:
        """Get a specific proposal by ID and type."""
        if not self.session:
            raise RuntimeError("Client must be used as an async context manager")
            
        try:
            endpoint = "polls" if proposal_type == "poll" else "executive"
            async with self.session.get(f"{self.base_url}/api/{endpoint}/{proposal_id}") as response:
                if response.status == 404:
                    return None
                response.raise_for_status()
                return await response.json()
        except Exception as e:
            logger.error(f"Error fetching proposal {proposal_id}: {e}")
            return None
    
    def parse_proposal(self, data: Dict, proposal_type: str) -> SkyProposal:
        """Parse API response into a SkyProposal object."""
        try:
            # Common fields
            proposal_id = data.get("key", "") if proposal_type == "executive" else str(data.get("pollId", ""))
            title = data.get("title", "")
            description = data.get("proposalBlurb", "") if proposal_type == "executive" else title
            
            # Parse timestamps
            if proposal_type == "executive":
                start_time = datetime.fromisoformat(data.get("date", "").replace("Z", "+00:00"))
                end_time = None
                if data.get("spellData", {}).get("expiration"):
                    end_time = datetime.fromisoformat(data.get("spellData", {}).get("expiration", "").replace("Z", "+00:00"))
            else:
                start_time = datetime.fromisoformat(data.get("startDate", "").replace("Z", "+00:00"))
                end_time = None
                if data.get("endDate"):
                    end_time = datetime.fromisoformat(data.get("endDate", "").replace("Z", "+00:00"))
            
            # Determine status
            status = "active"
            if proposal_type == "poll":
                if end_time and end_time < datetime.now():
                    status = "ended"
            else:  # executive vote
                spell_data = data.get("spellData", {})
                if spell_data.get("hasBeenCast"):
                    status = "executed"
                elif not data.get("active", True):
                    status = "passed"
            
            # Get support percentage for executive votes
            support = None
            if proposal_type == "executive":
                spell_data = data.get("spellData", {})
                if spell_data.get("skySupport"):
                    support = float(spell_data.get("skySupport", 0))
            
            # Construct proposal URL
            proposal_url = None
            if proposal_type == "executive":
                proposal_url = f"https://vote.sky.money/executive/{data.get('key', '')}"
            else:
                slug = data.get("slug")
                if slug:
                    proposal_url = f"https://vote.sky.money/polling/{slug}"
            
            return SkyProposal(
                id=proposal_id,
                title=title,
                description=description,
                status=status,
                start_time=start_time,
                end_time=end_time,
                proposal_url=proposal_url,
                type=proposal_type,
                support=support
            )
        except Exception as e:
            logger.error(f"Error parsing proposal data: {e}")
            raise 