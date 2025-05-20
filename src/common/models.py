from enum import Enum
from typing import Dict, Optional
from pydantic import BaseModel, Field


class PlatformType(str, Enum):
    TALLY = "tally"
    COSMOS = "cosmos"
    SPL = "spl"


class WatchlistItem(BaseModel):
    """Base model for items in the watchlist."""
    name: str
    platform: PlatformType
    platform_specific_id: str
    description: Optional[str] = None
    metadata: Dict = Field(default_factory=dict)


class Proposal(BaseModel):
    """Base model for governance proposals."""
    id: str
    title: str
    description: str
    platform: PlatformType
    platform_specific_id: str
    status: str
    created_at: str
    metadata: Dict = Field(default_factory=dict) 