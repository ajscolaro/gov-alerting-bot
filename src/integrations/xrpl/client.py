import asyncio
import logging
import time
from datetime import datetime
from typing import List, Dict, Optional, Any

import aiohttp
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

class XRPLAmendment(BaseModel):
    """Model for XRPL amendment data."""
    amendment_id: str
    name: str
    introduced: str
    enabled: bool
    supported: bool
    count: Optional[int] = None
    threshold: Optional[int] = None
    validations: Optional[int] = None
    enabled_on: Optional[str] = None
    tx_hash: Optional[str] = None
    majority: Optional[str] = None

    def is_active(self) -> bool:
        """Check if amendment is active (not enabled but supported)."""
        return not self.enabled and self.supported
    
    def has_ended(self) -> bool:
        """Check if amendment has ended (enabled)."""
        return self.enabled and self.enabled_on is not None

class XRPLClient:
    """Client for interacting with XRPScan API for XRPL amendments."""
    
    def __init__(self, metadata: Optional[Dict[str, Any]] = None):
        """Initialize client with metadata from watchlist."""
        # Use metadata if provided, otherwise use defaults
        if metadata and "api_url" in metadata:
            self.base_url = metadata["api_url"]
        else:
            self.base_url = "https://api.xrpscan.com"
        
        self.amendment_url_base = metadata.get("amendment_url", "https://xrpscan.com/amendment") if metadata else "https://xrpscan.com/amendment"
        
        self._session_instance = None
        self._min_request_interval = 1.0  # Minimum seconds between requests
        self._last_request_time = 0
        
        # Log initialization details
        logger.info(f"Initializing XRPLClient with:")
        logger.info(f"  Base URL: {self.base_url}")
        logger.info(f"  Amendment URL Base: {self.amendment_url_base}")
    
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
    
    async def get_amendments(self, tracked_amendments: Optional[Dict[str, Dict]] = None) -> List[XRPLAmendment]:
        """Fetch all amendments and check tracked amendments.
        
        Args:
            tracked_amendments: Optional dictionary of tracked amendments from state file.
                              If provided, will check these amendments for status changes.
        """
        try:
            # Fetch all amendments from the XRPScan API
            amendments = await self._fetch_amendments()
            
            # Check amendments that were previously alerted but might have ended
            ended_amendments = []
            if tracked_amendments:
                ended_amendments = await self._check_ended_amendments(tracked_amendments)
            
            # Combine the active and ended amendments
            all_amendments = amendments + ended_amendments
            
            # Log status counts
            active_count = sum(1 for a in all_amendments if a.is_active())
            ended_count = sum(1 for a in all_amendments if a.has_ended())
            
            logger.info(f"Found {len(all_amendments)} amendments: {active_count} active, {ended_count} ended")
            
            return all_amendments
        except Exception as e:
            logger.error(f"Error fetching amendments: {e}")
            return []
    
    async def _fetch_amendments(self) -> List[XRPLAmendment]:
        """Fetch all amendments from XRPScan API."""
        amendments = []
        session = await self._session()
        
        url = f"{self.base_url}/api/v1/amendments"
        logger.info(f"Fetching amendments from: {url}")
        
        try:
            await self._wait_for_rate_limit()
            
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=60)) as response:
                logger.debug(f"Response content-type: {response.headers.get('content-type')}")
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Failed to fetch amendments: {response.status} - {error_text}")
                    return []
                
                data = await response.json(content_type=None)
                
                if not isinstance(data, list):
                    logger.error(f"Unexpected response format: expected list, got {type(data)}")
                    return []
                
                for amendment_data in data:
                    try:
                        amendment = self._parse_amendment(amendment_data)
                        amendments.append(amendment)
                    except Exception as e:
                        logger.error(f"Error parsing amendment {amendment_data.get('amendment_id', 'unknown')}: {e}")
                        continue
                
                logger.info(f"Successfully fetched {len(amendments)} amendments")
                return amendments
                
        except asyncio.TimeoutError:
            logger.error(f"Timeout fetching amendments from {url}")
            return []
        except Exception as e:
            logger.error(f"Error fetching amendments: {e}")
            return []
    
    async def _check_ended_amendments(self, tracked_amendments: Dict[str, Dict]) -> List[XRPLAmendment]:
        """Check tracked amendments for status changes."""
        ended_amendments = []
        
        for amendment_id, tracked_data in tracked_amendments.items():
            # Only check amendments that were previously active (not enabled)
            if tracked_data.get("enabled", True):
                continue
            
            try:
                # Fetch individual amendment details
                amendment = await self.get_amendment_by_id(amendment_id)
                if amendment and amendment.has_ended():
                    ended_amendments.append(amendment)
                    logger.info(f"Amendment {amendment_id} has ended (enabled)")
            except Exception as e:
                logger.error(f"Error checking amendment {amendment_id}: {e}")
                continue
        
        return ended_amendments
    
    async def get_amendment_by_id(self, amendment_id: str) -> Optional[XRPLAmendment]:
        """Fetch a specific amendment by ID."""
        session = await self._session()
        
        url = f"{self.base_url}/api/v1/amendment/{amendment_id}"
        logger.info(f"Fetching amendment {amendment_id} from: {url}")
        
        try:
            await self._wait_for_rate_limit()
            
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=60)) as response:
                logger.debug(f"Response content-type: {response.headers.get('content-type')}")
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Failed to fetch amendment {amendment_id}: {response.status} - {error_text}")
                    return None
                
                data = await response.json(content_type=None)
                amendment = self._parse_amendment(data)
                return amendment
                
        except asyncio.TimeoutError:
            logger.error(f"Timeout fetching amendment {amendment_id}")
            return None
        except Exception as e:
            logger.error(f"Error fetching amendment {amendment_id}: {e}")
            return None
    
    def _parse_amendment(self, amendment_data: Dict[str, Any]) -> XRPLAmendment:
        """Parse amendment data from API response."""
        return XRPLAmendment(
            amendment_id=amendment_data.get("amendment_id", ""),
            name=amendment_data.get("name", ""),
            introduced=amendment_data.get("introduced", ""),
            enabled=amendment_data.get("enabled", False),
            supported=amendment_data.get("supported", False),
            count=amendment_data.get("count"),
            threshold=amendment_data.get("threshold"),
            validations=amendment_data.get("validations"),
            enabled_on=amendment_data.get("enabled_on"),
            tx_hash=amendment_data.get("tx_hash"),
            majority=amendment_data.get("majority")
        )
    
    def get_amendment_url(self, amendment_id: str) -> str:
        """Generate URL for viewing amendment on XRPScan."""
        return f"{self.amendment_url_base}/{amendment_id}"
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._session_instance:
            await self._session_instance.close()
            self._session_instance = None 