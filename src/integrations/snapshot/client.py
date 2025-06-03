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

    async def validate_space(self, space: str, max_retries: int = 3) -> Optional[bool]:
        """Validate if a space exists in Snapshot with proper error handling and retries.
        
        Args:
            space: The space ID to validate
            max_retries: Maximum number of retries for non-rate-limit errors
            
        Returns:
            Optional[bool]: 
                - True if space exists
                - False if space confirmed invalid
                - None if error occurred (not necessarily invalid)
        """
        query = """
        query Space($id: String!) {
          space(id: $id) {
            id
            name
          }
        }
        """
        
        variables = {"id": space}
        retries = 0
        
        while retries <= max_retries:
            try:
                async with asyncio.timeout(30):  # 30 second timeout
                    async with self.session.post(
                        self.base_url,
                        json={"query": query, "variables": variables},
                        headers=self.headers
                    ) as response:
                        response.raise_for_status()
                        data = await response.json()
                        
                        if "errors" in data:
                            # Check if it's a rate limit error
                            for error in data.get("errors", []):
                                if "Too Many Requests" in str(error):
                                    logger.warning(f"Rate limited while validating space {space}, will retry")
                                    raise aiohttp.ClientResponseError(
                                        status=429,
                                        message="Too Many Requests",
                                        request_info=None,
                                        history=None
                                    )
                            # For other GraphQL errors, log but don't treat as space not found
                            logger.error(f"GraphQL errors validating space {space}: {data['errors']}")
                            return None
                        
                        # If space doesn't exist, the space field will be null
                        space_data = data.get("data", {}).get("space")
                        if space_data is None:
                            logger.info(f"Space {space} confirmed not found")
                            return False
                            
                        logger.info(f"Space {space} validated successfully")
                        return True
                        
            except asyncio.TimeoutError:
                logger.error(f"Timeout validating space {space}")
                if retries < max_retries:
                    retries += 1
                    await asyncio.sleep(2 ** retries)  # Exponential backoff
                    continue
                return None
                
            except aiohttp.ClientResponseError as e:
                if e.status == 429:
                    # Re-raise rate limit errors to be handled by the rate limiter
                    raise
                logger.error(f"HTTP error validating space {space}: {str(e)}")
                if retries < max_retries:
                    retries += 1
                    await asyncio.sleep(2 ** retries)  # Exponential backoff
                    continue
                return None
                
            except Exception as e:
                logger.error(f"Unexpected error validating space {space}: {str(e)}")
                if retries < max_retries:
                    retries += 1
                    await asyncio.sleep(2 ** retries)  # Exponential backoff
                    continue
                return None
                
        logger.error(f"Max retries exceeded validating space {space}")
        return None

    async def get_active_proposals(self, space: str) -> Optional[List[Dict]]:
        """Get active proposals for a space. Returns:
        - None if there was an error (not necessarily space not found)
        - [] if the space exists but has no active proposals
        - List of proposals if the space exists and has active proposals
        """
        # First validate the space exists
        space_valid = await self.validate_space(space)
        if space_valid is False:  # Explicitly False means space doesn't exist
            return None
        elif space_valid is None:  # None means error occurred
            logger.error(f"Error validating space {space}, skipping proposal fetch")
            return None
            
        # Space exists, proceed with fetching proposals
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
                # Check if it's a rate limit error
                for error in response.get("errors", []):
                    if "Too Many Requests" in str(error):
                        logger.warning(f"Rate limited while getting proposals for {space}, will retry")
                        raise aiohttp.ClientResponseError(
                            status=429,
                            message="Too Many Requests",
                            request_info=None,
                            history=None
                        )
                # For other GraphQL errors, log but return None (error occurred)
                logger.error(f"GraphQL errors getting proposals for {space}: {response['errors']}")
                return None
                
            return response.get("data", {}).get("proposals", [])
            
        except aiohttp.ClientResponseError as e:
            if e.status == 429:
                # Re-raise rate limit errors to be handled by the rate limiter
                raise
            logger.error(f"Error getting active proposals for space {space}: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting active proposals for space {space}: {str(e)}")
            return None

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
                # Check if it's a rate limit error
                for error in response.get("errors", []):
                    if "Too Many Requests" in str(error):
                        logger.warning(f"Rate limited while getting proposal {proposal_id}, will retry")
                        raise aiohttp.ClientResponseError(
                            status=429,
                            message="Too Many Requests",
                            request_info=None,
                            history=None
                        )
                # For other GraphQL errors, log but don't treat as proposal not found
                logger.error(f"GraphQL error getting proposal {proposal_id}: {response['errors']}")
                return None
                
            proposal = response.get("data", {}).get("proposal")
            if proposal is None:
                logger.info(f"Proposal {proposal_id} not found in Snapshot")
            return proposal
            
        except aiohttp.ClientResponseError as e:
            if e.status == 429:
                # Re-raise rate limit errors to be handled by the rate limiter
                raise
            logger.error(f"HTTP error getting proposal {proposal_id}: {str(e)}")
            return None
        except Exception as e:
            # For unexpected errors, log but don't treat as proposal not found
            logger.error(f"Unexpected error getting proposal {proposal_id}: {str(e)}")
            return None

    async def check_proposal_exists(self, proposal_id: str) -> bool:
        """Check if a proposal still exists"""
        proposal = await self.get_proposal(proposal_id)
        return proposal is not None

    async def get_proposals_by_ids(self, proposal_ids: List[str]) -> Dict[str, Dict]:
        """Get multiple proposals by their IDs in a single query."""
        if not proposal_ids:
            return {}
            
        query = """
        query Proposals($ids: [String!]!) {
          proposals(
            where: {
              id_in: $ids
            }
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
        
        variables = {"ids": proposal_ids}
        try:
            response = await self._make_request(query, variables)
            
            if "errors" in response:
                # Check if it's a rate limit error
                for error in response.get("errors", []):
                    if "Too Many Requests" in str(error):
                        logger.warning(f"Rate limited while getting proposals {proposal_ids}, will retry")
                        raise aiohttp.ClientResponseError(
                            status=429,
                            message="Too Many Requests",
                            request_info=None,
                            history=None
                        )
                # For other GraphQL errors, log but return empty dict
                logger.error(f"GraphQL errors: {response['errors']}")
                return {}
                
            # Convert list to dict for easier lookup
            proposals = response.get("data", {}).get("proposals", [])
            return {p["id"]: p for p in proposals}
            
        except aiohttp.ClientResponseError as e:
            if e.status == 429:
                # Re-raise rate limit errors to be handled by the rate limiter
                raise
            logger.error(f"Error getting proposals {proposal_ids}: {str(e)}")
            return {}
        except Exception as e:
            logger.error(f"Unexpected error getting proposals {proposal_ids}: {str(e)}")
            return {} 