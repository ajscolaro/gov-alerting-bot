# Governance Alert Bot

A Python bot that monitors governance proposals from Tally, Cosmos SDK platforms, and Snapshot, sending alerts to Slack.

## Features

- Monitors governance proposals from:
  - Tally (Ethereum/EVM governance)
  - Cosmos SDK (Cosmos Hub, Osmosis, Celestia, and other Cosmos chains)
  - Snapshot (Off-chain governance platforms)
- Sends alerts to Slack for:
  - New active proposals 
  - Proposal status updates
  - Ended proposals
  - Deleted proposals (Snapshot)
- Thread management: Updates and end states are sent as thread replies to the original alert
- Consistent message formatting with action buttons to view proposals
- Rate-limited API calls to respect platform restrictions
- Configurable polling intervals
- Comprehensive error handling and logging
- Modular design allowing independent monitoring of each platform

## Documentation

- [Snapshot Integration](docs/snapshot_integration.md) - Details about Snapshot integration, alert types, and monitoring
- [Cosmos Integration](docs/cosmos_integration.md) - Information about Cosmos SDK chain monitoring and API handling
- [Tally Integration](docs/tally_integration.md) - Details about Tally governance monitoring and alerts

## Project Structure

```
.
├── data/
│   ├── watchlists/              # Configuration for projects to monitor
│   │   ├── tally_watchlist.json    # Tally projects configuration
│   │   ├── cosmos_watchlist.json   # Cosmos networks configuration
│   │   └── snapshot_watchlist.json # Snapshot spaces configuration
│   ├── proposal_tracking/       # State tracking for proposals
│   │   ├── tally_proposal_state.json    # Tally proposals state
│   │   ├── cosmos_proposal_state.json   # Cosmos proposals state
│   │   ├── snapshot_proposal_state.json # Snapshot proposals state
│   │   └── admin_alerts.json           # Tracks alerts that require admin action, like invalid space ids
│   └── test_proposal_tracking/  # Test state tracking
│       ├── tally_proposal_state.json    # Test state for Tally
│       ├── cosmos_proposal_state.json   # Test state for Cosmos
│       └── snapshot_proposal_state.json # Test state for Snapshot
├── src/
│   ├── common/
│   │   ├── alerts/            # Common alert handling code
│   │   │   ├── base.py       # Base alert handler
│   │   │   └── slack.py      # Slack alert sender
│   │   ├── models.py         # Shared data models
│   │   ├── config.py         # Configuration handling
│   │   └── __init__.py
│   ├── integrations/
│   │   ├── cosmos/           # Cosmos SDK integration
│   │   │   ├── client.py     # API client for Cosmos chains
│   │   │   ├── alerts.py     # Alert formatting for Cosmos
│   │   │   └── __init__.py
│   │   ├── tally/            # Tally integration
│   │   │   ├── client.py     # API client for Tally
│   │   │   ├── alerts.py     # Alert formatting for Tally
│   │   │   └── __init__.py
│   │   └── snapshot/         # Snapshot integration
│   │       ├── client.py     # API client for Snapshot
│   │       ├── alerts.py     # Alert formatting for Snapshot
│   │       └── __init__.py
│   ├── monitor/              # Monitoring scripts
│   │   ├── monitor_tally.py  # Tally monitoring script
│   │   ├── monitor_cosmos.py # Cosmos monitoring script
│   │   ├── monitor_snapshot.py # Snapshot monitoring script
│   │   └── __init__.py
│   ├── monitor.py            # Main monitoring script (runs all monitors)
│   └── __init__.py
├── docs/                     # Documentation
│   ├── snapshot_integration.md
│   ├── cosmos_integration.md
│   └── tally_integration.md
├── .env                    # Environment configuration
├── requirements.txt        # Production dependencies
└── requirements-dev.txt    # Development dependencies
```

## Quick Start

1. Create a Python virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file with your configuration:
```env
SLACK_BOT_TOKEN=xoxb-your-token
SLACK_CHANNEL=your-channel-id
TEST_SLACK_CHANNEL=your-test-channel-id  # Optional: Channel for testing individual monitors
TALLY_API_KEY=your-tally-api-key
CHECK_INTERVAL=60  # Polling interval in seconds
```

4. Set up data files:
   - Create the required directories:
     ```bash
     mkdir -p data/watchlists data/proposal_tracking data/test_proposal_tracking
     ```
   - Create empty state files:
     ```json
     # data/proposal_tracking/tally_proposal_state.json
     {}
     ```
     ```json
     # data/proposal_tracking/cosmos_proposal_state.json
     {}
     ```
     ```json
     # data/proposal_tracking/snapshot_proposal_state.json
     {}
     ```
     ```json
     # data/proposal_tracking/admin_alerts.json
     {}
     ```
   - Create watchlist files following the configuration guide in each integration's documentation

5. Run the monitoring scripts:
```bash
# Run all monitors
python src/monitor.py

# Run specific monitors
python src/monitor.py --monitors tally cosmos snapshot

# Run individual monitors directly (for testing)
python src/monitor/monitor_tally.py
python src/monitor/monitor_cosmos.py
python src/monitor/monitor_snapshot.py

# Run in continuous mode (all monitors)
python src/monitor.py --continuous

# Run specific monitors in continuous mode
python src/monitor.py --continuous --monitors tally cosmos snapshot
```

## Common Features

### Slack Alert Formatting

All Slack alerts use a modern, consistent format:
- **Title:** Displayed in a header block (large, prominent)
- **Description/Body:** Displayed in a context block (smaller, lighter font)
- **Divider:** Visually separates the content from actions
- **Button:** Action button (e.g., "View Proposal") shown below the divider

Example Slack Block structure:
```json
[
  { "type": "header", "text": { "type": "plain_text", "text": "Project Proposal Active", "emoji": true } },
  { "type": "context", "elements": [ { "type": "mrkdwn", "text": "MIP 103 - Incentives Distribution on Unichain" } ] },
  { "type": "divider" },
  { "type": "actions", "elements": [ { "type": "button", "text": { "type": "plain_text", "text": "View Proposal", "emoji": true }, "url": "https://..." } ] }
]
```

### State Management
- Each platform maintains its own state file in `data/proposal_tracking/`
- Test state files are in `data/test_proposal_tracking/`
- Admin alerts are tracked in `data/proposal_tracking/admin_alerts.json`
- State files are automatically created if they don't exist
- Proposals are tracked with unique identifiers
- Thread context is preserved for all status updates
- Proposals are automatically removed after reaching final states

### Error Handling and Logging
- Comprehensive error handling at multiple levels
- Detailed logging with timestamps and log levels
- Failed alerts are logged but don't stop the monitoring process
- Automatic retry with backoff for network errors
- State files are preserved even if the bot crashes
- 60-second timeouts for RPC calls (including fallback attempts)
- 30-second timeouts for Slack API calls
- Graceful handling of RPC endpoint failures

### Rate Limiting
- Configurable polling intervals via environment variables
- Automatic waiting between requests to respect rate limits
- Platform-specific rate limits are documented in each integration's documentation

For detailed information about each integration's specific features, configuration, and monitoring behavior, please refer to the respective documentation files in the `docs/` directory. 