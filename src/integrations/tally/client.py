import asyncio
import time
import os
from typing import List, Dict, Any, Optional
import aiohttp
from pydantic import BaseModel

class TallyProposal(BaseModel):
    """Model for Tally proposal data."""
    id: str
    title: str
    status: str
    proposal_url: str
    discourse_url: Optional[str] = None
    snapshot_url: Optional[str] = None
    governor_slug: str
    created_at: Optional[str] = None

class TallyClient:
    """Client for interacting with Tally API."""
    
    def __init__(self):
        self.api_url = "https://api.tally.xyz/query"
        self.api_key = os.getenv("TALLY_API_KEY")
        if not self.api_key:
            raise ValueError("TALLY_API_KEY environment variable is not set")
        self._last_request_time = 0
        self._min_request_interval = 1.0  # Changed from 2.0 to 1.0 second
    
    async def _wait_for_rate_limit(self):
        """Ensure we respect rate limits by waiting if necessary."""
        current_time = time.time()
        time_since_last_request = current_time - self._last_request_time
        if time_since_last_request < self._min_request_interval:
            await asyncio.sleep(self._min_request_interval - time_since_last_request)
        self._last_request_time = time.time()
    
    async def get_proposals(self, governor_address: str, chain_id: str) -> List[TallyProposal]:
        """Fetch proposals for a specific governor."""
        await self._wait_for_rate_limit()
        
        query = """
        query GetProposals($input: ProposalsInput!) {
            proposals(input: $input) {
                nodes {
                    ... on Proposal {
                        id
                        status
                        governor {
                            slug
                        }
                        metadata {
                            title
                            discourseURL
                            snapshotURL
                        }
                        events {
                            type
                            createdAt
                        }
                    }
                }
            }
        }
        """
        
        variables = {
            "input": {
                "filters": {
                    "governorId": f"{chain_id}:{governor_address}"
                }
            }
        }
        
        headers = {
            "Content-Type": "application/json",
            "Api-Key": self.api_key
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.api_url,
                json={"query": query, "variables": variables},
                headers=headers
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Failed to fetch proposals: {response.status} - {error_text}")
                
                data = await response.json()
                if "errors" in data:
                    raise Exception(f"GraphQL errors: {data['errors']}")
                
                proposals_data = data["data"]["proposals"]["nodes"]
                return [TallyProposal(
                    id=p["id"],
                    title=p["metadata"]["title"],
                    status=p["status"],
                    proposal_url="",  # We'll construct this in the alert handler
                    discourse_url=p["metadata"].get("discourseURL"),
                    snapshot_url=p["metadata"].get("snapshotURL"),
                    governor_slug=p["governor"]["slug"],
                    created_at=next((e["createdAt"] for e in p["events"] if e["type"] == "created"), None)
                ) for p in proposals_data]
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass 