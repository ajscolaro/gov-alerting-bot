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
- Unified state tracking across different platforms

## Project Structure

```
.
├── data/
│   ├── proposal_state.json    # Unified state tracking for all platforms
│   └── watchlist.json         # Configuration for platforms and networks to monitor
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
│   ├── monitor.py            # Main monitoring script
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
CHECK_INTERVAL=60  # Tally polling interval in seconds
COSMOS_CHECK_INTERVAL=300  # Cosmos polling interval in seconds
```

4. Set up data files:
   - Create a `data` directory in the project root
   - Create `data/proposal_state.json` with an empty object:
     ```json
     {
       "tally": {},
       "cosmos": {}
     }
     ```
   - Create `data/watchlist.json` following the configuration guide below

5. Run the monitoring script:
```bash
python src/monitor.py
```

## Data Files

The bot uses two JSON files for state management and configuration:

### proposal_state.json

This file tracks the state of all monitored proposals. It's automatically created and managed by the bot. The initial structure should be:

```json
{
  "tally": {},
  "cosmos": {}
}
```

The bot will automatically populate this file as it monitors proposals. Each proposal's state includes:
- Current status
- Thread timestamp for Slack messages
- Alert status

### watchlist.json

This file defines which projects and networks to monitor. Here's the structure for each supported platform:

### Tally Projects

```json
{
  "tally": [
    {
      "name": "Example Protocol",
      "platform_specific_id": "example-protocol",
      "description": "Example Protocol Governance",
      "metadata": {
        "type": "protocol",
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
- `platform_specific_id`: Unique identifier
- `metadata.governor_address`: Tally governor contract address
- `metadata.chain_id`: Chain ID in eip155 format
- `metadata.token_address`: Governance token address
- `metadata.tally_url`: Tally governance page URL

### Cosmos Networks

```json
{
  "cosmos": [
    {
      "name": "Example Network",
      "platform_specific_id": "example-network",
      "description": "Example Network Governance",
      "metadata": {
        "type": "network",
        "chain_id": "example-1",
        "rpc_url": "https://rest.cosmos.directory/example",
        "explorer_url": "https://www.mintscan.io/example"
      }
    }
  ]
}
```

Required fields for Cosmos networks:
- `name`: Display name for the network
- `platform_specific_id`: Unique identifier (typically the network name)
- `metadata.chain_id`: Chain ID (e.g., "cosmoshub-4")
- `metadata.rpc_url`: REST API URL
- `metadata.explorer_url`: Block explorer URL

Optional fields for Cosmos networks:
- `metadata.explorer_type`: Type of explorer to use (default: "mintscan")
  - "mintscan": For networks supported by Mintscan
  - "pingpub": For networks using Ping.pub explorer
- `metadata.explorer_name`: Display name for the explorer (default: "Mintscan")

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
2. The Slack message timestamp is stored in `proposal_state.json`
3. Status updates and ended alerts are sent as thread replies
4. Thread replies are broadcast to the channel with `reply_broadcast=true`
5. Proposals are removed from state tracking after their final status alert

## API Rate Limiting

The bot implements rate limiting to respect platform API restrictions:
- Tally API: 1 request per 1 second
- Cosmos REST APIs: No specific limit enforced, but 1 second intervals between requests
- Automatic waiting between requests
- Configurable polling intervals via environment variables

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

MIT 