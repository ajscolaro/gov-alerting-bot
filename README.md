# Governance Alert Bot

A Python bot that monitors governance proposals from Tally, Cosmos SDK platforms, and Snapshot, sending alerts to Slack.

## Features

- Monitors governance proposals from:
  - Tally (Ethereum/EVM governance)
  - Cosmos SDK (Cosmos Hub, Osmosis, Celestia, and other Cosmos chains)
  - Snapshot (Off-chain governance platforms)
  - Sky Protocol (Polls and Executive votes)
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
- [Sky Integration](docs/sky_integration.md) - Information about Sky Protocol monitoring and alert handling

## Project Structure

```
.
├── data/
│   ├── watchlists/              # Configuration for projects to monitor
│   │   ├── tally_watchlist.json    # Tally projects configuration
│   │   ├── cosmos_watchlist.json   # Cosmos networks configuration
│   │   ├── snapshot_watchlist.json # Snapshot spaces configuration
│   │   └── sky_watchlist.json      # Sky Protocol configuration
│   ├── proposal_tracking/       # State tracking for proposals
│   │   ├── tally_proposal_state.json    # Tally proposals state
│   │   ├── cosmos_proposal_state.json   # Cosmos proposals state
│   │   ├── snapshot_proposal_state.json # Snapshot proposals state
│   │   ├── sky_proposal_state.json      # Sky proposals state
│   │   └── admin_alerts.json           # Tracks alerts that require admin action, like invalid space ids
│   └── test_proposal_tracking/  # Test state tracking
│       ├── tally_proposal_state.json    # Test state for Tally
│       ├── cosmos_proposal_state.json   # Test state for Cosmos
│       ├── snapshot_proposal_state.json # Test state for Snapshot
│       └── sky_proposal_state.json      # Test state for Sky
├── src/
│   ├── common/
│   │   ├── alerts/            # Common alert handling code
│   │   │   ├── base.py       # Base alert handler
│   │   │   └── slack.py      # Slack alert sender
│   │   ├── models.py         # Shared data models
│   │   ├── config.py         # Configuration handling
│   │   ├── sheets/           # Google Sheets integration
│   │   │   ├── client.py     # Google Sheets API client
│   │   │   ├── models.py     # Data models for sheet rows
│   │   │   └── sync.py       # Watchlist sync logic
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
│   │   ├── snapshot/         # Snapshot integration
│   │   │   ├── client.py     # API client for Snapshot
│   │   │   ├── alerts.py     # Alert formatting for Snapshot
│   │   │   └── __init__.py
│   │   └── sky/              # Sky Protocol integration
│   │       ├── client.py     # API client for Sky
│   │       ├── alerts.py     # Alert formatting for Sky
│   │       └── __init__.py
│   ├── monitor/              # Monitoring scripts
│   │   ├── monitor_tally.py  # Tally monitoring script
│   │   ├── monitor_cosmos.py # Cosmos monitoring script
│   │   ├── monitor_snapshot.py # Snapshot monitoring script
│   │   ├── monitor_sky.py    # Sky monitoring script
│   │   └── __init__.py
│   ├── monitor.py            # Main monitoring script (runs all monitors)
│   └── __init__.py
├── docs/                     # Documentation
│   ├── snapshot_integration.md
│   ├── cosmos_integration.md
│   ├── tally_integration.md
│   └── sky_integration.md
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
TEST_TALLY_API_KEY=your-test-tally-api-key  # Optional: API key for testing
CHECK_INTERVAL=60  # Polling interval in seconds
TEST_CHECK_INTERVAL=60  # Optional: Polling interval for test mode
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
     # data/proposal_tracking/sky_proposal_state.json
     {}
     ```
     ```json
     # data/proposal_tracking/admin_alerts.json
     {}
     ```
   - Create watchlist files following the configuration guide in each integration's documentation

5. Run the monitoring scripts:
```bash
# Run all monitors in production mode (continuous)
python src/monitor.py

# Run specific monitors in production mode
python src/monitor.py --monitors tally cosmos snapshot sky

# Run individual monitors in test mode (runs once and exits)
python src/monitor/monitor_tally.py
python src/monitor/monitor_cosmos.py
python src/monitor/monitor_snapshot.py
python src/monitor/monitor_sky.py
```

Note: When running through `monitor.py`, all monitors run continuously in production mode. When running individual monitor scripts directly, they run in test mode (once and exit).

## Google Sheets Watchlist Sync

This project supports syncing watchlists from a Google Sheet, allowing you to manage Tally, Cosmos, Snapshot, and Sky integrations in one place.

### Setup Steps

1. **Create a Google Cloud Project and Service Account**
   - Go to https://console.cloud.google.com/
   - Create a new project (or use an existing one)
   - Enable the Google Sheets API
   - Create a service account and download the credentials JSON file

2. **Share Your Google Sheet**
   - Create a Google Sheet with separate tabs named `Tally`, `Cosmos`, `Snapshot`, and `Sky`
   - Add the required columns for each integration (see below)
   - Share the sheet with your service account's email (found in the credentials JSON)

3. **Store Credentials Securely**
   - Place the credentials file at `data/watchlists/govbot-google-sheets-credentials.json`
   - Add this line to your `.env` file:
     ```env
     GOOGLE_SHEETS_CREDENTIALS=data/watchlists/govbot-google-sheets-credentials.json
     ```
   - Ensure the credentials file is listed in `.gitignore`

4. **Set Up Your Sheet Tabs**
   - **Tally:**
     ```
     name | description | intel_label | chain | governor_address | chain_id | token_address | tally_url
     ```
   - **Cosmos:**
     ```
     name | description | intel_label | chain_id | rpc_url | explorer_url | fallback_rpc_url | explorer_type
     ```
   - **Snapshot:**
     ```
     name | description | intel_label | space | snapshot_url
     ```
   - **Sky:**
     ```
     name | description | intel_label | poll_url | executive_url
     ```

5. **Run the Sync Script**
   - Activate your virtual environment
   - Run:
     ```bash
     ./src/scripts/sync_watchlists.py \
       --spreadsheet-id <YOUR_SPREADSHEET_ID> \
       --watchlist-dir data/watchlists \
       --last-sync-file data/watchlists/.last_sync \
       --force \
       --verbose
     ```
   - The script will use the credentials path from your `.env` if `--credentials` is not specified.

6. **Automate (Optional)**
   - Add a cron job to run the sync script daily to keep your watchlists up to date.

### Notes
- The script will update `data/watchlists/tally_watchlist.json`, `cosmos_watchlist.json`, etc. to match your Google Sheet.
- The sync logic uses a unique key for each integration (e.g., `chain:governor_address` for Tally) to determine adds/updates/removals.
- Always keep your sheet columns in the expected order for each integration.

## Common Features

### Alert Routing
The bot uses the `intel_label` field in watchlist files to determine which Slack channel to send alerts to:
- `"app"`: Alerts are sent to the application governance channel
- `"net"`: Alerts are sent to the network governance channel

This routing is consistent across all integrations (Tally, Cosmos, Snapshot, Sky) and applies to:
- Initial proposal alerts
- Status update alerts
- Ended proposal alerts
- All alerts maintain thread context in their respective channels

Example watchlist entry:
```json
{
  "name": "Example Protocol",
  "description": "Example Protocol Governance",
  "intel_label": "app",  // or "net" for network governance
  "metadata": {
    // integration-specific metadata
  }
}
```

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
- Each platform maintains its own state file in `data/proposal_tracking/` for production
- Test state files are in `data/test_proposal_tracking/` for testing
- State files are automatically created if they don't exist
- Production mode is used when running through `monitor.py`
- Test mode is used when running individual monitor scripts directly
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