# Governance Alert Bot

A Python bot that monitors governance proposals from Tally and Cosmos SDK platforms and sends alerts to Slack. Additional platform integrations (Aragon, Sky) are currently under development.

## Features

- Monitors governance proposals from:
  - Tally (Ethereum/EVM governance)
  - Cosmos SDK (Cosmos Hub, Osmosis, Celestia, and other Cosmos chains)
  - Additional platforms under development
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
│   │   └── models.py          # Shared data models
│   ├── integrations/
│   │   ├── tally/             # Tally-specific integration
│   │   └── cosmos/            # Cosmos SDK integration
│   ├── monitor.py             # Main monitoring script
│   └── cosmos_monitor.py      # Cosmos monitoring specific code
├── tests/                     # Test suite
├── .env                       # Environment configuration
├── requirements.txt           # Production dependencies
└── requirements-dev.txt       # Development dependencies
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

This file defines which projects and networks to monitor. See the Watchlist Configuration section below for details.

## Watchlist Configuration

The watchlist.json file defines which projects and networks to monitor. Here's the structure for each supported platform:

### Tally Projects

```json
{
  "tally": [
    {
      "name": "Project Name",
      "platform_specific_id": "project-id",
      "description": "Project Description",
      "metadata": {
        "type": "protocol",
        "chain": "ethereum",
        "governor_address": "0x...",
        "chain_id": "eip155:1",
        "token_address": "0x...",
        "tally_url": "https://www.tally.xyz/gov/..."
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
      "name": "Network Name",
      "platform_specific_id": "network-id",
      "description": "Network Description",
      "metadata": {
        "type": "network",
        "chain_id": "chain-id",
        "rpc_url": "https://rest.cosmos.directory/network",
        "explorer_url": "https://www.mintscan.io/network"
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

Example for a Ping.pub network:
```json
{
  "name": "Terra",
  "platform_specific_id": "terra",
  "description": "Terra Network Governance",
  "metadata": {
    "type": "network",
    "chain_id": "phoenix-1",
    "rpc_url": "https://rest.cosmos.directory/terra2",
    "explorer_url": "https://ping.pub/terra/gov",
    "explorer_type": "pingpub",
    "explorer_name": "Ping.pub"
  }
}
```

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

## Development

1. Install development dependencies:
```bash
pip install -r requirements-dev.txt
```

2. Run tests:
```bash
pytest tests/ -v
```

3. Add new platforms:
   - Create a new directory in `src/integrations/`
   - Implement a client, alert handler, and models
   - Update `watchlist.json` with the new platform section
   - Add the platform to the monitoring loop in `monitor.py`

## Troubleshooting

- **Missing thread replies**: Check if the proposal state contains a valid `thread_ts`
- **Rate limit errors**: Increase the `_min_request_interval` in the client
- **API version errors**: Some Cosmos chains use v1 instead of v1beta1 APIs
- **Notification issues**: Ensure the Slack bot has permissions for the channel
- **Missing proposals**: Check the console logs for API errors

## Tips

- The bot tracks proposal status in `data/proposal_state.json` with sections for each platform
- Use `reply_broadcast=True` to ensure thread replies are visible in the channel
- New platform integrations should follow the pattern of existing ones
- Add `framework` parameter when storing/retrieving proposal data in different sections
- Use consistent message formatting across all platforms for better user experience

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and code quality checks
5. Submit a pull request

## License

MIT 