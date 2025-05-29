# Governance Alert Bot

A Python bot that monitors governance proposals from Tally and Cosmos SDK platforms and sends alerts to Slack.

## Features

- Monitors governance proposals from:
  - Tally (Ethereum/EVM governance)
  - Cosmos SDK (Cosmos Hub, Osmosis, Celestia, and other Cosmos chains)
- Sends alerts to Slack for:
  - New active proposals 
  - Proposal status updates
  - Ended proposals
- Thread management: Updates and end states are sent as thread replies to the original alert
- Consistent message formatting with action buttons to view proposals
- Rate-limited API calls to respect platform restrictions
- Configurable polling intervals
- Comprehensive error handling and logging
- Modular design allowing independent monitoring of each platform

## Project Structure

```
.
├── data/
│   ├── watchlists/              # Configuration for projects to monitor
│   │   ├── tally_watchlist.json    # Tally projects configuration
│   │   └── cosmos_watchlist.json   # Cosmos networks configuration
│   └── proposal_tracking/       # State tracking for proposals
│       ├── tally_proposal_state.json    # Tally proposals state
│       └── cosmos_proposal_state.json   # Cosmos proposals state
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
│   │   └── tally/            # Tally integration
│   │       ├── client.py     # API client for Tally
│   │       ├── alerts.py     # Alert formatting for Tally
│   │       └── __init__.py
│   ├── monitor/              # Monitoring scripts
│   │   ├── monitor_tally.py  # Tally monitoring script
│   │   ├── monitor_cosmos.py # Cosmos monitoring script
│   │   └── __init__.py
│   ├── monitor.py            # Main monitoring script (runs all monitors)
│   └── __init__.py
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
TALLY_API_KEY=your-tally-api-key
CHECK_INTERVAL=60  # Polling interval in seconds
```

4. Set up data files:
   - Create the required directories:
     ```bash
     mkdir -p data/watchlists data/proposal_tracking
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
   - Create watchlist files following the configuration guide below

5. Run the monitoring scripts:
```bash
# Run all monitors
python src/monitor.py

# Run specific monitors
python src/monitor.py --monitors tally
python src/monitor.py --monitors cosmos

# Run individual monitors directly
python src/monitor/monitor_tally.py
python src/monitor/monitor_cosmos.py
```

## Important Notes

### Python Path and Imports
The project uses relative imports and automatically adds the project root to the Python path. This allows running scripts from any directory while maintaining proper module resolution. The path is added in each script using:
```python
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
```

### State Management
- Each platform (Tally and Cosmos) maintains its own state file
- State files are automatically created if they don't exist
- Proposals are tracked with unique identifiers combining network/project ID and proposal ID
- Thread context is preserved for all status updates
- Proposals are automatically removed from tracking after reaching final states

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
- Tally API: 1 request per 1 second
- Cosmos REST APIs: 1 second intervals between requests
- Configurable polling intervals via environment variables
- Automatic waiting between requests to respect rate limits

### Cosmos Integration Specifics
- The Cosmos monitor automatically handles both v1 and v1beta1 API versions
- If a v1 endpoint returns 501 (Not Implemented), it falls back to v1beta1
- Some Cosmos chains may only support v1beta1 endpoints
- RPC endpoints may occasionally be slow or unresponsive
- Consider using fallback RPCs for chains with reliability issues
- When using a fallback RPC, both v1 and v1beta1 endpoints are tried on the fallback URL
- The monitor will only skip a chain if both endpoints fail on both primary and fallback URLs
- Each RPC attempt (primary and fallback) has up to 60 seconds to complete
- SSL errors may appear in logs during timeouts but are handled gracefully

## Data Files

The bot uses separate JSON files for state management and configuration:

### State Files

Each platform has its own state file that tracks the proposals being monitored:

- `data/proposal_tracking/tally_proposal_state.json`: Tracks Tally proposals
- `data/proposal_tracking/cosmos_proposal_state.json`: Tracks Cosmos proposals

Each proposal's state includes:
- Current status
- Thread timestamp for Slack messages
- Alert status

Example state file structure:
```json
{
  "proposal_id": {
    "status": "active",
    "thread_ts": "1234567890.123456",
    "alerted": true
  }
}
```

### Watchlist Files

Each platform has its own watchlist file that defines which projects and networks to monitor:

### Tally Projects (data/watchlists/tally_watchlist.json)

```json
{
  "projects": [
    {
      "name": "Example Protocol",
      "description": "Example Protocol Governance",
      "intel_label": "app",
      "metadata": {
        "chain": "ethereum",
        "governor_address": "0x1234...",
        "chain_id": "eip155:1",
        "token_address": "0x5678...",
        "tally_url": "https://www.tally.xyz/gov/example"
      }
    }
  ]
}
```

Required fields for Tally projects:
- `name`: Display name for the project
- `description`: Brief description of the project
- `intel_label`: Category label (e.g., "app" for applications, "net" for networks)
- `metadata.chain`: Chain name (e.g., "ethereum", "arbitrum", "base")
- `metadata.governor_address`: Tally governor contract address
- `metadata.chain_id`: Chain ID in eip155 format
- `metadata.token_address`: Governance token address
- `metadata.tally_url`: Tally governance page URL

### Cosmos Networks (data/watchlists/cosmos_watchlist.json)

```json
{
  "projects": [
    {
      "name": "Example Network",
      "description": "Example Network Governance",
      "metadata": {
        "type": "network",
        "chain_id": "example-1",
        "rpc_url": "https://rest.cosmos.directory/example",
        "explorer_url": "https://www.mintscan.io/example",
        "explorer_type": "mintscan",  # Optional: "mintscan" or "pingpub" for URL formatting
        "fallback_rpc_url": "https://alternative-rpc.example"  # Optional: Fallback RPC URL
      }
    }
  ]
}
```

Required fields for Cosmos networks:
- `name`: Display name for the network
- `metadata.chain_id`: Chain ID (e.g., "cosmoshub-4")
- `metadata.rpc_url`: REST API URL
- `metadata.explorer_url`: Block explorer URL

Optional fields for Cosmos networks:
- `metadata.fallback_rpc_url`: Fallback REST API URL to use if the primary RPC is unavailable or slow
  - Recommended for chains with known reliability issues
  - Should be from a different provider than the primary RPC
  - Will be used automatically if primary RPC fails
- `metadata.explorer_type`: Type of explorer to use (default: "mintscan")
  - "mintscan": For networks supported by Mintscan
  - "pingpub": For networks using Ping.pub explorer

## Alert Types

### Tally Alerts

1. **Proposal Active**
   - New proposal detected in active state
   - Includes link to view on Tally
   - Starting point for thread notifications

2. **Proposal Update**
   - Status change (e.g., to extended)
   - Sent as thread reply to original alert

3. **Proposal Ended**
   - Final status (succeeded, defeated, etc.)
   - Sent as thread reply
   - Automatically removes proposal from tracking

### Cosmos Alerts

1. **Proposal Voting**
   - New proposal in voting period
   - Includes link to view on Mintscan
   - Starting point for thread notifications

2. **Proposal Ended**
   - Voting period ended
   - Sent as thread reply
   - Automatically removes proposal from tracking

## Thread Management

The bot maintains thread context for each proposal:

1. Initial alerts create a new message
2. The Slack message timestamp is stored in the platform-specific state file
3. Status updates and ended alerts are sent as thread replies
4. Thread replies are broadcast to the channel with `reply_broadcast=true`
5. Proposals are removed from state tracking after their final status alert

## Implementation Details

### State Management
- Each platform uses a separate state file to track proposals
- State files are automatically created if they don't exist
- State is persisted between bot restarts
- Proposals are removed from tracking after reaching final states

### Error Handling
- Comprehensive error handling at multiple levels:
  - Individual proposal processing
  - Network/API calls
  - State file operations
- Failed alerts are logged but don't stop the monitoring process
- Automatic retry with backoff for network errors

### Rate Limiting
- Tally API: 1 request per 1 second
- Cosmos REST APIs: 1 second intervals between requests
- Configurable polling intervals via environment variables
- Automatic waiting between requests to respect rate limits

### Monitoring Modes
- Can run individual monitors or all monitors together
- Command-line arguments to select which monitors to run
- Independent state tracking for each platform
- Parallel execution of monitors when running multiple

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

MIT 