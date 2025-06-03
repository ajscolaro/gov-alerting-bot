#!/usr/bin/env python3
"""CLI script for syncing watchlists from Google Sheets."""

import argparse
import logging
import os
import sys
from pathlib import Path

# Add src directory to Python path
src_dir = Path(__file__).parent.parent.parent
sys.path.append(str(src_dir))

from src.common.sheets.client import GoogleSheetsClient
from src.common.sheets.sync import WatchlistSync

def setup_logging(verbose: bool):
    """Set up logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Sync watchlists from Google Sheets")
    parser.add_argument(
        "--credentials",
        default=os.getenv("GOOGLE_SHEETS_CREDENTIALS"),
        required=(os.getenv("GOOGLE_SHEETS_CREDENTIALS") is None),
        help="Path to Google service account credentials JSON file (or set GOOGLE_SHEETS_CREDENTIALS env var)"
    )
    parser.add_argument(
        "--spreadsheet-id",
        required=True,
        help="Google Spreadsheet ID"
    )
    parser.add_argument(
        "--watchlist-dir",
        default="data/watchlists",
        help="Directory containing watchlist files (default: data/watchlists)"
    )
    parser.add_argument(
        "--last-sync-file",
        default="data/watchlists/.last_sync",
        help="File to track last sync time (default: data/watchlists/.last_sync)"
    )
    parser.add_argument(
        "--sync-interval",
        type=int,
        default=24,
        help="Hours between syncs (default: 24)"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force sync regardless of last sync time"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    return parser.parse_args()

def main():
    """Main entry point."""
    args = parse_args()
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)

    try:
        # Initialize Google Sheets client
        client = GoogleSheetsClient(args.credentials, args.spreadsheet_id)

        # Initialize watchlist sync
        sync = WatchlistSync(
            sheets_client=client,
            watchlist_dir=args.watchlist_dir,
            last_sync_file=args.last_sync_file,
            sync_interval_hours=args.sync_interval
        )

        # Run sync
        results = sync.sync(force=args.force)
        
        if not results:
            logger.info("No sync performed - too soon since last sync")
            return

        # Print summary
        print("\nSync Summary:")
        print("-" * 50)
        for integration_type, (added, updated, removed) in results.items():
            print(f"{integration_type.value}:")
            print(f"  Added: {added}")
            print(f"  Updated: {updated}")
            print(f"  Removed: {removed}")
            print()

    except Exception as e:
        logger.error(f"Error during sync: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 