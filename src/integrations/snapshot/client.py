import aiohttp
import asyncio
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

class SnapshotClient:
    """Client for interacting with Snapshot API"""
    
    def __init__(self):
        self.base_url = "https://hub.snapshot.org/graphql"
        self.headers = {
            "Content-Type": "application/json",
        }
        self.session = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
            
    async def _make_request(self, query: str, variables: Optional[Dict] = None) -> Dict:
        """Make a GraphQL request to Snapshot API"""
        try:
            async with asyncio.timeout(30):  # 30 second timeout
                async with self.session.post(
                    self.base_url,
                    json={"query": query, "variables": variables},
                    headers=self.headers
                ) as response:
                    response.raise_for_status()
                    return await response.json()
        except asyncio.TimeoutError:
            logger.error("Timeout making request to Snapshot API")
            raise
        except aiohttp.ClientError as e:
            logger.error(f"Error making request to Snapshot API: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error making request to Snapshot API: {str(e)}")
            raise

    async def get_active_proposals(self, space: str) -> List[Dict]:
        """Get active proposals for a space"""
        query = """
        query Proposals($space: String!) {
          proposals(
            first: 1000,
            where: {
              space_in: [$space],
              state: "active"
            },
            orderBy: "created",
            orderDirection: desc
          ) {
            id
            title
            body
            choices
            start
            end
            snapshot
            state
            author
            space {
              id
              name
            }
          }
        }
        """
        
        variables = {"space": space}
        try:
            response = await self._make_request(query, variables)
            
            if "errors" in response:
                logger.error(f"GraphQL errors: {response['errors']}")
                return []
                
            return response.get("data", {}).get("proposals", [])
        except Exception as e:
            logger.error(f"Error getting active proposals for space {space}: {str(e)}")
            return []

    async def get_proposal(self, proposal_id: str) -> Optional[Dict]:
        """Get a specific proposal by ID"""
        query = """
        query Proposal($id: String!) {
          proposal(id: $id) {
            id
            title
            body
            choices
            start
            end
            snapshot
            state
            author
            space {
              id
              name
            }
          }
        }
        """
        
        variables = {"id": proposal_id}
        try:
            response = await self._make_request(query, variables)
            
            if "errors" in response:
                logger.error(f"GraphQL errors: {response['errors']}")
                return None
                
            return response.get("data", {}).get("proposal")
        except Exception as e:
            logger.error(f"Error getting proposal {proposal_id}: {str(e)}")
            return None

    async def check_proposal_exists(self, proposal_id: str) -> bool:
        """Check if a proposal still exists"""
        proposal = await self.get_proposal(proposal_id)
        return proposal is not None 