"""Data models for Google Sheets watchlist synchronization."""

from dataclasses import dataclass
from typing import Dict, List, Optional
from enum import Enum

class IntegrationType(Enum):
    """Supported integration types."""
    TALLY = "tally"
    COSMOS = "cosmos"
    SNAPSHOT = "snapshot"
    SKY = "sky"
    XRPL = "xrpl"

@dataclass
class WatchlistItem:
    """Base class for watchlist items."""
    name: str
    description: str
    intel_label: str
    metadata: Dict[str, str]

@dataclass
class TallyWatchlistItem(WatchlistItem):
    """Tally-specific watchlist item."""
    chain: str
    governor_address: str
    chain_id: str
    token_address: str
    tally_url: str

    @classmethod
    def from_sheet_row(cls, row: List[str]) -> 'TallyWatchlistItem':
        """Create a TallyWatchlistItem from a sheet row.
        
        Expected columns:
        0: name
        1: description
        2: intel_label
        3: chain
        4: governor_address
        5: chain_id
        6: token_address
        7: tally_url
        """
        if len(row) < 8:
            raise ValueError(f"Invalid row length: {len(row)}")
        
        return cls(
            name=row[0],
            description=row[1],
            intel_label=row[2],
            metadata={},
            chain=row[3],
            governor_address=row[4],
            chain_id=row[5],
            token_address=row[6],
            tally_url=row[7]
        )

    def to_dict(self) -> Dict:
        """Convert to dictionary format for watchlist file."""
        return {
            "name": self.name,
            "description": self.description,
            "intel_label": self.intel_label,
            "metadata": {
                "chain": self.chain,
                "governor_address": self.governor_address,
                "chain_id": self.chain_id,
                "token_address": self.token_address,
                "tally_url": self.tally_url
            }
        }

@dataclass
class CosmosWatchlistItem(WatchlistItem):
    """Cosmos-specific watchlist item."""
    chain_id: str
    rpc_url: str
    explorer_url: str
    fallback_rpc_url: Optional[str] = None
    explorer_type: Optional[str] = None

    @classmethod
    def from_sheet_row(cls, row: List[str]) -> 'CosmosWatchlistItem':
        """Create a CosmosWatchlistItem from a sheet row.
        
        Expected columns:
        0: name
        1: description
        2: intel_label
        3: chain_id
        4: rpc_url
        5: explorer_url
        6: fallback_rpc_url (optional)
        7: explorer_type (optional)
        """
        if len(row) < 6:
            raise ValueError(f"Invalid row length: {len(row)}")
        
        return cls(
            name=row[0],
            description=row[1],
            intel_label=row[2],
            metadata={},
            chain_id=row[3],
            rpc_url=row[4],
            explorer_url=row[5],
            fallback_rpc_url=row[6] if len(row) > 6 else None,
            explorer_type=row[7] if len(row) > 7 else None
        )

    def to_dict(self) -> Dict:
        """Convert to dictionary format for watchlist file."""
        metadata = {
            "chain_id": self.chain_id,
            "rpc_url": self.rpc_url,
            "explorer_url": self.explorer_url
        }
        if self.fallback_rpc_url:
            metadata["fallback_rpc_url"] = self.fallback_rpc_url
        if self.explorer_type:
            metadata["explorer_type"] = self.explorer_type
            
        return {
            "name": self.name,
            "description": self.description,
            "intel_label": self.intel_label,
            "metadata": metadata
        }

@dataclass
class SnapshotWatchlistItem(WatchlistItem):
    """Snapshot-specific watchlist item."""
    space: str
    snapshot_url: str

    @classmethod
    def from_sheet_row(cls, row: List[str]) -> 'SnapshotWatchlistItem':
        """Create a SnapshotWatchlistItem from a sheet row.
        
        Expected columns:
        0: name
        1: description
        2: intel_label
        3: space
        4: snapshot_url
        """
        if len(row) < 5:
            raise ValueError(f"Invalid row length: {len(row)}")
        
        return cls(
            name=row[0],
            description=row[1],
            intel_label=row[2],
            metadata={},
            space=row[3],
            snapshot_url=row[4]
        )

    def to_dict(self) -> Dict:
        """Convert to dictionary format for watchlist file."""
        return {
            "name": self.name,
            "description": self.description,
            "intel_label": self.intel_label,
            "metadata": {
                "space": self.space,
                "snapshot_url": self.snapshot_url
            }
        }

@dataclass
class SkyWatchlistItem(WatchlistItem):
    """Sky-specific watchlist item."""
    poll_url: str
    executive_url: str

    @classmethod
    def from_sheet_row(cls, row: List[str]) -> 'SkyWatchlistItem':
        """Create a SkyWatchlistItem from a sheet row.
        
        Expected columns:
        0: name
        1: description
        2: intel_label
        3: poll_url
        4: executive_url
        """
        if len(row) < 5:
            raise ValueError(f"Invalid row length: {len(row)}")
        
        return cls(
            name=row[0],
            description=row[1],
            intel_label=row[2],
            metadata={},
            poll_url=row[3],
            executive_url=row[4]
        )

    def to_dict(self) -> Dict:
        """Convert to dictionary format for watchlist file."""
        return {
            "name": self.name,
            "description": self.description,
            "intel_label": self.intel_label,
            "metadata": {
                "poll_url": self.poll_url,
                "executive_url": self.executive_url
            }
        }

@dataclass
class XRPLWatchlistItem(WatchlistItem):
    """XRPL-specific watchlist item."""
    api_url: str
    amendment_url: str

    @classmethod
    def from_sheet_row(cls, row: List[str]) -> 'XRPLWatchlistItem':
        """Create an XRPLWatchlistItem from a sheet row.
        
        Expected columns:
        0: name
        1: description
        2: intel_label
        3: api_url
        4: amendment_url
        5: metadata (optional)
        """
        if len(row) < 5:
            raise ValueError(f"Invalid row length: {len(row)}")
        
        return cls(
            name=row[0],
            description=row[1],
            intel_label=row[2],
            metadata={},
            api_url=row[3],
            amendment_url=row[4]
        )

    def to_dict(self) -> Dict:
        """Convert to dictionary format for watchlist file."""
        return {
            "name": self.name,
            "description": self.description,
            "intel_label": self.intel_label,
            "metadata": {
                "api_url": self.api_url,
                "amendment_url": self.amendment_url
            }
        } 