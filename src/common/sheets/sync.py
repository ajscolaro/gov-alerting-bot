"""Watchlist synchronization logic."""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from .client import GoogleSheetsClient
from .models import (
    IntegrationType,
    TallyWatchlistItem,
    CosmosWatchlistItem,
    SnapshotWatchlistItem,
    SkyWatchlistItem,
    XRPLWatchlistItem,
    WatchlistItem
)

logger = logging.getLogger(__name__)

class WatchlistSync:
    """Handles synchronization of watchlists from Google Sheets."""

    # Mapping of integration types to their sheet names and item classes
    INTEGRATION_CONFIG = {
        IntegrationType.TALLY: ("Tally", TallyWatchlistItem),
        IntegrationType.COSMOS: ("Cosmos", CosmosWatchlistItem),
        IntegrationType.SNAPSHOT: ("Snapshot", SnapshotWatchlistItem),
        IntegrationType.SKY: ("Sky", SkyWatchlistItem),
        IntegrationType.XRPL: ("XRPL", XRPLWatchlistItem)
    }

    def __init__(
        self,
        sheets_client: GoogleSheetsClient,
        watchlist_dir: str,
        last_sync_file: str,
        sync_interval_hours: int = 24
    ):
        """Initialize the watchlist sync.
        
        Args:
            sheets_client: Google Sheets client instance
            watchlist_dir: Directory containing watchlist files
            last_sync_file: Path to file tracking last sync time
            sync_interval_hours: Hours between syncs (default: 24)
        """
        self.sheets_client = sheets_client
        self.watchlist_dir = Path(watchlist_dir)
        self.last_sync_file = Path(last_sync_file)
        self.sync_interval = timedelta(hours=sync_interval_hours)

    def _should_sync(self) -> bool:
        """Check if a sync should be performed based on last sync time."""
        if not self.last_sync_file.exists():
            return True

        try:
            with open(self.last_sync_file, 'r') as f:
                last_sync = datetime.fromisoformat(f.read().strip())
            return datetime.now() - last_sync >= self.sync_interval
        except Exception as e:
            logger.warning(f"Error reading last sync time: {e}")
            return True

    def _update_last_sync_time(self):
        """Update the last sync time file."""
        try:
            with open(self.last_sync_file, 'w') as f:
                f.write(datetime.now().isoformat())
        except Exception as e:
            logger.error(f"Error updating last sync time: {e}")

    def _load_current_watchlist(self, integration_type: IntegrationType) -> Dict:
        """Load current watchlist from file."""
        watchlist_file = self.watchlist_dir / f"{integration_type.value}_watchlist.json"
        try:
            if watchlist_file.exists():
                with open(watchlist_file, 'r') as f:
                    return json.load(f)
            return {"projects": []}
        except Exception as e:
            logger.error(f"Error loading watchlist {watchlist_file}: {e}")
            return {"projects": []}

    def _save_watchlist(self, integration_type: IntegrationType, data: Dict):
        """Save watchlist to file."""
        watchlist_file = self.watchlist_dir / f"{integration_type.value}_watchlist.json"
        try:
            with open(watchlist_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving watchlist {watchlist_file}: {e}")
            raise

    def _get_sheet_items(
        self,
        integration_type: IntegrationType
    ) -> List[WatchlistItem]:
        """Get items from the integration's sheet."""
        sheet_name, item_class = self.INTEGRATION_CONFIG[integration_type]
        try:
            # Skip header row
            rows = self.sheets_client.get_sheet_data(sheet_name)[1:]
            items = []
            for row in rows:
                try:
                    items.append(item_class.from_sheet_row(row))
                except Exception as e:
                    logger.error(f"Error parsing row in {sheet_name}: {e}")
                    continue
            return items
        except Exception as e:
            logger.error(f"Error getting sheet data for {sheet_name}: {e}")
            return []

    def _get_item_key(self, item: WatchlistItem, integration_type: IntegrationType) -> str:
        """Get unique key for a watchlist item."""
        if integration_type == IntegrationType.TALLY:
            return f"{item.chain}:{item.governor_address}"
        elif integration_type == IntegrationType.COSMOS:
            return item.chain_id
        elif integration_type == IntegrationType.SNAPSHOT:
            return item.space
        elif integration_type == IntegrationType.SKY:
            return item.name
        elif integration_type == IntegrationType.XRPL:
            return item.name
        return item.name

    def _reconstruct_item(self, item_class, p: dict) -> WatchlistItem:
        """Reconstruct a watchlist item from JSON dict, unpacking metadata."""
        base_args = {
            'name': p.get('name', ''),
            'description': p.get('description', ''),
            'intel_label': p.get('intel_label', ''),
            'metadata': p.get('metadata', {})
        }
        meta = p.get('metadata', {})
        if item_class.__name__ == 'TallyWatchlistItem':
            return item_class(
                **base_args,
                chain=meta.get('chain', ''),
                governor_address=meta.get('governor_address', ''),
                chain_id=meta.get('chain_id', ''),
                token_address=meta.get('token_address', ''),
                tally_url=meta.get('tally_url', '')
            )
        elif item_class.__name__ == 'CosmosWatchlistItem':
            return item_class(
                **base_args,
                chain_id=meta.get('chain_id', ''),
                rpc_url=meta.get('rpc_url', ''),
                explorer_url=meta.get('explorer_url', ''),
                fallback_rpc_url=meta.get('fallback_rpc_url'),
                explorer_type=meta.get('explorer_type')
            )
        elif item_class.__name__ == 'SnapshotWatchlistItem':
            return item_class(
                **base_args,
                space=meta.get('space', ''),
                snapshot_url=meta.get('snapshot_url', '')
            )
        elif item_class.__name__ == 'SkyWatchlistItem':
            return item_class(
                **base_args,
                poll_url=meta.get('poll_url', ''),
                executive_url=meta.get('executive_url', '')
            )
        elif item_class.__name__ == 'XRPLWatchlistItem':
            return item_class(
                **base_args,
                api_url=meta.get('api_url', ''),
                amendment_url=meta.get('amendment_url', '')
            )
        else:
            return item_class(**base_args)

    def _sync_integration(self, integration_type: IntegrationType) -> Tuple[int, int, int]:
        """Sync a single integration's watchlist.
        
        Returns:
            Tuple of (added, updated, removed) counts
        """
        current_data = self._load_current_watchlist(integration_type)
        _, item_class = self.INTEGRATION_CONFIG[integration_type]
        current_items = {
            self._get_item_key(self._reconstruct_item(item_class, p), integration_type): p
            for p in current_data.get("projects", [])
        }

        sheet_items = self._get_sheet_items(integration_type)
        sheet_keys = {self._get_item_key(item, integration_type) for item in sheet_items}

        added = 0
        updated = 0
        removed = 0

        # Process additions and updates
        for item in sheet_items:
            key = self._get_item_key(item, integration_type)
            if key not in current_items:
                current_items[key] = item.to_dict()
                added += 1
            elif current_items[key] != item.to_dict():
                current_items[key] = item.to_dict()
                updated += 1

        # Process removals
        removed_keys = set(current_items.keys()) - sheet_keys
        for key in removed_keys:
            del current_items[key]
            removed += 1

        # Save updated watchlist
        self._save_watchlist(integration_type, {"projects": list(current_items.values())})

        return added, updated, removed

    def sync(self, force: bool = False) -> Dict[IntegrationType, Tuple[int, int, int]]:
        """Sync all watchlists from Google Sheets.
        
        Args:
            force: If True, sync regardless of last sync time
            
        Returns:
            Dict mapping integration types to (added, updated, removed) counts
        """
        if not force and not self._should_sync():
            logger.info("Skipping sync - too soon since last sync")
            return {}

        results = {}
        try:
            for integration_type in IntegrationType:
                logger.info(f"Syncing {integration_type.value} watchlist...")
                results[integration_type] = self._sync_integration(integration_type)
                added, updated, removed = results[integration_type]
                logger.info(
                    f"{integration_type.value} sync complete: "
                    f"{added} added, {updated} updated, {removed} removed"
                )

            self._update_last_sync_time()
            return results
        except Exception as e:
            logger.error(f"Error during sync: {e}")
            raise 