import asyncio
import logging
import os
import sys
import argparse
from typing import List

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.alerts.slack import SlackAlertSender
from common.alerts.base import AlertConfig
from monitor.monitor_tally import monitor_tally_proposals
from monitor.monitor_cosmos import monitor_cosmos_proposals
from monitor.monitor_snapshot import monitor_snapshot_proposals
from monitor.monitor_sky import monitor_sky_proposals

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def run_monitors(monitors: List[str]):
    """Run the specified monitoring tasks."""
    # Load configuration from environment variables
    config = AlertConfig(
        slack_bot_token=os.getenv("SLACK_BOT_TOKEN"),
        slack_channel=os.getenv("SLACK_CHANNEL"),  # Use production channel
        disable_link_previews=True,
        enabled_alert_types=["proposal_active", "proposal_update", "proposal_ended",
                           "proposal_voting", "proposal_ended", "proposal_deleted",
                           "space_not_detected"]
    )
    
    if not config.slack_bot_token or not config.slack_channel:
        logger.error("Missing required environment variables: SLACK_BOT_TOKEN and/or SLACK_CHANNEL")
        return
    
    # Get check interval from environment
    check_interval = int(os.getenv("CHECK_INTERVAL", "60"))  # Default to 60 seconds if not set
    
    # Initialize components
    slack_sender = SlackAlertSender(config)
    
    # Run selected monitoring tasks in parallel
    tasks = []
    if "tally" in monitors:
        logger.info("Starting Tally monitor")
        tasks.append(monitor_tally_proposals(slack_sender, continuous=True, check_interval=check_interval))
    if "cosmos" in monitors:
        logger.info("Starting Cosmos monitor")
        tasks.append(monitor_cosmos_proposals(slack_sender, continuous=True, check_interval=check_interval))
    if "snapshot" in monitors:
        logger.info("Starting Snapshot monitor")
        tasks.append(monitor_snapshot_proposals(slack_sender, continuous=True, check_interval=check_interval))
    if "sky" in monitors:
        logger.info("Starting Sky monitor")
        tasks.append(monitor_sky_proposals(slack_sender, continuous=True, check_interval=check_interval))
    
    if not tasks:
        logger.error("No valid monitors specified")
        return
    
    try:
        await asyncio.gather(*tasks)
    except KeyboardInterrupt:
        logger.info("Monitoring stopped by user")
    except Exception as e:
        logger.error(f"Monitoring stopped due to error: {e}")

async def main():
    """Main entry point."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Governance Alert Bot")
    parser.add_argument(
        "--monitors",
        nargs="+",
        choices=["tally", "cosmos", "snapshot", "sky"],
        default=["tally", "cosmos", "snapshot", "sky"],
        help="Specify which monitors to run (default: all)"
    )
    args = parser.parse_args()

    # Ensure data directories exist
    os.makedirs("data/watchlists", exist_ok=True)
    os.makedirs("data/proposal_tracking", exist_ok=True)
    os.makedirs("data/test_proposal_tracking", exist_ok=True)
    
    await run_monitors(args.monitors)

if __name__ == "__main__":
    asyncio.run(main()) 