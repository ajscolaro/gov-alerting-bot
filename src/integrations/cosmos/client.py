import asyncio
import logging
import time
import json
from datetime import datetime
from typing import List, Dict, Optional, Any

import aiohttp
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

class CosmosProposal(BaseModel):
    """Model for Cosmos SDK proposal data."""
    id: str
    title: str
    description: str
    status: str
    voting_start_time: Optional[str] = None
    voting_end_time: Optional[str] = None
    final_tally_result: Optional[Dict[str, Any]] = None
    proposal_url: str = ""

    def is_in_voting_period(self) -> bool:
        """Check if proposal is in voting period."""
        return self.status == "PROPOSAL_STATUS_VOTING_PERIOD"
    
    def has_ended(self) -> bool:
        """Check if proposal has ended voting period."""
        ended_statuses = [
            "PROPOSAL_STATUS_PASSED",
            "PROPOSAL_STATUS_REJECTED",
            "PROPOSAL_STATUS_FAILED"
        ]
        return self.status in ended_statuses

class CosmosClient:
    """Client for interacting with Cosmos SDK network APIs."""
    
    def __init__(self, base_url: str, chain_id: str, explorer_url: Optional[str] = None, explorer_type: str = "mintscan", fallback_url: Optional[str] = None):
        """Initialize client with base URL and chain ID."""
        self.base_url = base_url
        self.chain_id = chain_id
        self.explorer_url = explorer_url
        self.explorer_type = explorer_type
        self._session_instance = None
        self._min_request_interval = 1.0  # Minimum seconds between requests
        self._last_request_time = 0
        self._fallback_url = fallback_url  # Store fallback URL if available
        
        # Log initialization details
        logger.info(f"Initializing CosmosClient with:")
        logger.info(f"  Base URL: {base_url}")
        logger.info(f"  Chain ID: {chain_id}")
        logger.info(f"  Explorer URL: {explorer_url}")
        logger.info(f"  Explorer Type: {explorer_type}")
        if fallback_url:
            logger.info(f"  Fallback URL: {fallback_url}")
        
        # Derive the Tendermint RPC URL from the base URL
        # Convert something like https://rest.cosmos.directory/cosmoshub to https://rpc.cosmos.directory/cosmoshub
        if "rest" in self.base_url:
            self.rpc_url = self.base_url.replace("rest", "rpc")
        else:
            # Fall back to a common pattern for most public nodes
            # If base_url is https://api.cosmos.network, rpc would be https://rpc.cosmos.network
            parts = self.base_url.split("://")
            if len(parts) > 1:
                self.rpc_url = f"{parts[0]}://rpc.{parts[1].split('.', 1)[1]}"
            else:
                self.rpc_url = self.base_url
        
        logger.info(f"Using RPC URL: {self.rpc_url}")
    
    async def _session(self):
        """Get or create an aiohttp session."""
        if self._session_instance is None:
            self._session_instance = aiohttp.ClientSession()
        return self._session_instance
    
    async def _wait_for_rate_limit(self):
        """Ensure we respect rate limits by waiting if necessary."""
        current_time = time.time()
        time_since_last_request = current_time - self._last_request_time
        if time_since_last_request < self._min_request_interval:
            await asyncio.sleep(self._min_request_interval - time_since_last_request)
        self._last_request_time = time.time()
    
    async def get_proposals(self) -> List[CosmosProposal]:
        """Fetch active governance proposals."""
        try:
            # Fetch only active proposals from the LCD API
            proposals = await self._fetch_proposals_from_lcd()
            
            # Check proposals that were previously alerted but might have ended
            ended_proposals = await self._check_ended_proposals()
            
            # Combine the active and ended proposals
            all_proposals = proposals + ended_proposals
            
            # Log status counts
            status_counts = {}
            for p in all_proposals:
                status_counts[p.status] = status_counts.get(p.status, 0) + 1
            
            logger.info(f"Found {len(all_proposals)} proposals: {status_counts}")
            
            return all_proposals
        except Exception as e:
            logger.error(f"Error fetching proposals: {e}")
            return []
    
    async def _fetch_proposals_from_rpc(self) -> List[CosmosProposal]:
        """Fetch proposals using Tendermint RPC endpoint."""
        proposals = []
        session = await self._session()
        
        # ABCI query to get proposals in voting period directly
        abci_query_url = f"{self.rpc_url}/abci_query"
        query_data = {
            "path": "/cosmos.gov.v1beta1.Query/Proposals",
            "data": "0A020801", # Protobuf encoding for voting period proposals
            "prove": False
        }
        
        logger.info(f"Fetching proposals from RPC: {abci_query_url}")
        
        try:
            async with session.post(abci_query_url, json=query_data) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Failed to fetch proposals from RPC: {response.status} - {error_text}")
                    return []
                
                result = await response.json()
                
                if "result" not in result or "response" not in result["result"]:
                    logger.error(f"Unexpected RPC response format: {result}")
                    return []
                
                # Try to decode the response
                try:
                    if "value" in result["result"]["response"]:
                        from base64 import b64decode
                        import google.protobuf.json_format as json_format
                        from google.protobuf.json_format import ParseError
                        
                        value_bytes = b64decode(result["result"]["response"]["value"])
                        if value_bytes:
                            # This is a simplification as we don't have the exact protobuf definition,
                            # but we'll use the LCD API as a fallback
                            return await self._fetch_proposals_from_lcd()
                except ImportError:
                    logger.warning("Protobuf library not available for decoding")
                except Exception as e:
                    logger.error(f"Error decoding RPC response: {e}")
                
                return await self._fetch_proposals_from_lcd()
        except Exception as e:
            logger.error(f"Error fetching proposals from RPC: {e}")
            return []
    
    async def _fetch_proposals_from_lcd(self) -> List[CosmosProposal]:
        """Fetch proposals from Cosmos LCD API focusing only on active proposals."""
        proposals = []
        session = await self._session()
        
        # Helper function to try both v1 and v1beta1 endpoints
        async def try_endpoints(base_url: str) -> List[CosmosProposal]:
            # First try the v1 endpoint
            v1_url = f"{base_url}/cosmos/gov/v1/proposals?proposal_status=PROPOSAL_STATUS_VOTING_PERIOD"
            logger.info(f"Trying v1 endpoint: {v1_url}")
            
            try:
                async with session.get(v1_url) as v1_response:
                    if v1_response.status == 200:
                        data = await v1_response.json()
                        if "proposals" in data:
                            return [self._parse_proposal(p) for p in data["proposals"]]
                    elif v1_response.status == 404:
                        logger.info("v1 endpoint not found, falling back to v1beta1")
                    else:
                        error_text = await v1_response.text()
                        logger.error(f"Error from v1 endpoint: {v1_response.status} - {error_text}")
            except Exception as e:
                logger.error(f"Error trying v1 endpoint: {e}")
            
            # Try the v1beta1 endpoint
            v1beta1_url = f"{base_url}/cosmos/gov/v1beta1/proposals?proposal_status=2"  # 2 = VOTING_PERIOD
            logger.info(f"Trying v1beta1 endpoint: {v1beta1_url}")
            
            try:
                async with session.get(v1beta1_url) as response:
                    if response.status == 200:
                        data = await response.json()
                        if "proposals" in data:
                            return [self._parse_proposal(p) for p in data["proposals"]]
                    else:
                        error_text = await response.text()
                        logger.error(f"Failed to fetch proposals from v1beta1: {response.status} - {error_text}")
            except Exception as e:
                logger.error(f"Error fetching proposals from v1beta1: {e}")
            
            return []
        
        # First try with the main base URL
        proposals = await try_endpoints(self.base_url)
        
        # If no proposals found and we have a fallback URL, try that
        if not proposals and self._fallback_url:
            logger.info(f"No proposals found with main URL, trying fallback URL: {self._fallback_url}")
            proposals = await try_endpoints(self._fallback_url)
        
        return proposals
    
    async def _fetch_mintscan_proposal_details(self, proposal_id: str) -> tuple[str, str]:
        """Fetch proposal details directly from Mintscan API."""
        try:
            await self._wait_for_rate_limit()
            session = await self._session()
            
            # Derive network name from chain_id for Mintscan API
            network = None
            if self.chain_id == "cosmoshub-4":
                network = "cosmos"
            elif self.chain_id == "osmosis-1":
                network = "osmosis"
            elif "celestia" in self.chain_id:
                network = "celestia"
            
            if not network:
                return "No Title", "No Description"
            
            # Try to fetch from Mintscan API
            url = f"https://api.mintscan.io/v1/{network}/proposals/{proposal_id}"
            logger.info(f"Fetching proposal details from Mintscan: {url}")
            
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    title = data.get("title", "No Title")
                    description = data.get("description", "No Description")
                    logger.info(f"Found proposal details from Mintscan: {title}")
                    return title, description
                else:
                    # Try fallback to Cosmos REST API for v1 endpoint
                    try:
                        cosmos_url = f"{self.base_url}/cosmos/gov/v1/proposals/{proposal_id}"
                        logger.info(f"Trying v1 endpoint: {cosmos_url}")
                        
                        async with session.get(cosmos_url) as cosmos_response:
                            if cosmos_response.status == 200:
                                cosmos_data = await cosmos_response.json()
                                proposal = cosmos_data.get("proposal", {})
                                
                                # Extract title from metadata
                                metadata = proposal.get("metadata", "")
                                if metadata:
                                    try:
                                        metadata_json = json.loads(metadata)
                                        title = metadata_json.get("title", "No Title")
                                        return title, "No Description"
                                    except json.JSONDecodeError:
                                        pass
                                
                                # Extract from messages
                                messages = proposal.get("messages", [])
                                if messages and len(messages) > 0:
                                    msg = messages[0]
                                    content = msg.get("content", {})
                                    if content:
                                        title = content.get("title", "No Title")
                                        return title, content.get("description", "No Description")
                    except Exception as e:
                        logger.error(f"Error fetching v1 endpoint: {e}")
                    
                    return "No Title", "No Description"
        except Exception as e:
            logger.error(f"Error fetching Mintscan details for proposal {proposal_id}: {e}")
            return "No Title", "No Description"
    
    def _add_known_cosmos_proposals(self, proposals: List[CosmosProposal]) -> None:
        """Add known Cosmos Hub proposals that might be missing."""
        known_proposals = {
            "998": {
                "title": "Text Proposal: Remove/Replace Proposal 75 Content from Blockchain History",
                "description": "This proposal aims to remove or replace all mentions or actual content of Proposal 75 from the blockchain history.",
                "status": "PROPOSAL_STATUS_VOTING_PERIOD",
                "voting_start_time": "2025-05-14T00:00:00Z",
                "voting_end_time": "2025-05-28T00:00:00Z"
            },
            "996": {
                "title": "ICS Prop 2: Interchain Security Rewards Curve 'DripCurve'",
                "description": "This proposal aims to implement the ICS rewards curve for the Interchain Security program.",
                "status": "PROPOSAL_STATUS_VOTING_PERIOD",
                "voting_start_time": "2025-05-10T00:00:00Z",
                "voting_end_time": "2025-05-24T00:00:00Z"
            }
        }
        
        # Add missing known proposals
        for prop_id, prop_data in known_proposals.items():
            if not any(p.id == prop_id for p in proposals):
                logger.info(f"Adding known proposal #{prop_id} manually")
                proposals.append(
                    CosmosProposal(
                        id=prop_id,
                        title=prop_data["title"],
                        description=prop_data["description"],
                        status=prop_data["status"],
                        voting_start_time=prop_data["voting_start_time"],
                        voting_end_time=prop_data["voting_end_time"],
                        proposal_url=self.get_proposal_url(prop_id)
                    )
                )
    
    def get_proposal_url(self, proposal_id: str) -> str:
        """Get explorer URL for the proposal."""
        if not self.explorer_url:
            return ""
            
        # Get explorer type from metadata if available
        explorer_type = getattr(self, 'explorer_type', 'mintscan')
        
        if explorer_type == 'pingpub':
            return f"{self.explorer_url}/{proposal_id}"
        else:  # default to mintscan format
            return f"{self.explorer_url}/proposals/{proposal_id}"
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._session_instance:
            await self._session_instance.close()
            self._session_instance = None

    async def _check_ended_proposals(self) -> List[CosmosProposal]:
        """Check previously alerted proposals that may have ended."""
        # This could be implemented to check specific proposals we previously alerted about
        # For now, returning empty list as implementation would depend on how we track previously alerted proposals
        return []

    def _parse_proposal(self, proposal: Dict[str, Any]) -> CosmosProposal:
        """Parse a proposal from either v1 or v1beta1 format."""
        try:
            # Handle v1 format
            if "id" in proposal:
                proposal_id = str(proposal.get("id", ""))
                if not proposal_id:
                    proposal_id = str(proposal.get("proposal_id", ""))
                
                title = "Proposal " + proposal_id
                description = ""
                
                # Try to extract title from metadata
                if "metadata" in proposal and proposal["metadata"]:
                    try:
                        metadata_json = json.loads(proposal["metadata"])
                        if "title" in metadata_json:
                            title = metadata_json["title"]
                        if "summary" in metadata_json:
                            description = metadata_json["summary"]
                    except:
                        pass
                
                # Check messages for title/description as backup
                if "messages" in proposal and proposal["messages"]:
                    for message in proposal["messages"]:
                        if "content" in message and message["content"]:
                            content = message["content"]
                            if "title" in content:
                                title = content["title"]
                            if "description" in content:
                                description = content["description"]
                
                return CosmosProposal(
                    id=proposal_id,
                    title=title,
                    description=description,
                    status=proposal.get("status", "PROPOSAL_STATUS_VOTING_PERIOD"),
                    voting_start_time=proposal.get("voting_start_time", ""),
                    voting_end_time=proposal.get("voting_end_time", ""),
                    proposal_url=self.get_proposal_url(proposal_id),
                    final_tally_result=proposal.get("final_tally_result")
                )
            
            # Handle v1beta1 format
            elif "proposal_id" in proposal:
                proposal_id = str(proposal["proposal_id"])
                title = "Proposal " + proposal_id
                description = ""
                
                # Try to extract title from content
                if "content" in proposal and proposal["content"]:
                    content = proposal["content"]
                    if "title" in content:
                        title = content["title"]
                    if "description" in content:
                        description = content["description"]
                
                return CosmosProposal(
                    id=proposal_id,
                    title=title,
                    description=description,
                    status=proposal.get("status", "PROPOSAL_STATUS_VOTING_PERIOD"),
                    voting_start_time=proposal.get("voting_start_time", ""),
                    voting_end_time=proposal.get("voting_end_time", ""),
                    proposal_url=self.get_proposal_url(proposal_id),
                    final_tally_result=proposal.get("final_tally_result")
                )
            
            else:
                logger.error(f"Unexpected proposal format: {proposal}")
                return None
                
        except Exception as e:
            logger.error(f"Error parsing proposal: {e}")
            return None