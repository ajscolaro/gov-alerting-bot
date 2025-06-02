# Cosmos Integration Documentation

## Overview

The Cosmos integration monitors governance proposals across multiple Cosmos SDK chains, sending alerts for new proposals and ended proposals. The system is designed to handle both v1 and v1beta1 API versions, with fallback support for chains that only support v1beta1.

## Components

### 1. CosmosClient (`src/integrations/cosmos/client.py`)

The client handles all interactions with Cosmos REST APIs:

- **API Version Handling**: Automatically handles both v1 and v1beta1 API versions
- **Proposal Fetching**: 
  - `get_active_proposals`: Fetches proposals in voting period
  - `get_proposal`: Fetches details for a specific proposal
  - `get_proposals_by_ids`: Fetches multiple proposals in a single query
- **Error Handling**: Handles RPC errors, timeouts, and API version fallbacks
- **Fallback Support**: Automatically tries fallback RPCs if primary RPC fails

### 2. CosmosAlertHandler (`src/integrations/cosmos/alerts.py`)

Manages alert formatting and decision logic:

- **Alert Types**:
  - `proposal_voting`: New proposals in voting period
  - `proposal_ended`: Proposals that have closed

- **Alert Formatting**:
  - Each alert type has specific formatting for title, description, and action buttons
  - Thread context is maintained for proposal updates
  - Explorer links are formatted based on the chain's explorer type

### 3. Proposal Tracking (`src/monitor/monitor_cosmos.py`)

The monitor system manages proposal state and alert delivery:

#### State Management
- **Proposal State**: Tracks proposal status, thread timestamps, and alert history
- **Persistence**: State is saved to JSON files:
  - `data/proposal_tracking/cosmos_proposal_state.json` (production)
  - `data/test_proposal_tracking/cosmos_proposal_state.json` (testing)

#### Alert Processing
1. **New Proposals**:
   - Detected when a proposal isn't in the state file
   - Sends a new alert with a thread timestamp
   - Adds to tracking state

2. **Ended Proposals**:
   - Detected when a proposal's state changes from "voting" to "passed/failed/rejected"
   - Sends alert as a thread reply
   - Removes from tracking state

### 4. Watchlist Configuration (`data/watchlists/cosmos_watchlist.json`)

The watchlist defines which chains to monitor:

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
        "explorer_type": "mintscan",  # Optional: "mintscan" or "pingpub"
        "fallback_rpc_url": "https://alternative-rpc.example"  # Optional
      }
    }
  ]
}
```

Required fields:
- `name`: Display name for the network
- `metadata.chain_id`: Chain ID (e.g., "cosmoshub-4")
- `metadata.rpc_url`: REST API URL
- `metadata.explorer_url`: Block explorer URL

Optional fields:
- `metadata.fallback_rpc_url`: Fallback REST API URL
- `metadata.explorer_type`: Type of explorer ("mintscan" or "pingpub")

## Error Handling

### RPC Failures
1. When a primary RPC fails:
   - The system automatically tries the fallback RPC if configured
   - Both v1 and v1beta1 endpoints are tried on each RPC
   - Each RPC attempt has up to 60 seconds to complete
   - SSL errors during timeouts are handled gracefully

### API Version Handling
- Automatically detects API version support
- Falls back to v1beta1 if v1 returns 501 (Not Implemented)
- Some chains may only support v1beta1 endpoints
- Both versions are tried on fallback RPCs

## Performance Optimizations

### RPC Management
- Primary and fallback RPCs are tried in sequence
- 60-second timeouts for each RPC attempt
- Automatic fallback to v1beta1 if v1 is not supported
- Clear logging of RPC failures and fallbacks

### Proposal Fetching
- Only fetches proposals in voting period
- Direct proposal ID lookups for tracked proposals
- Efficient proposal status tracking
- Reduced API calls by only checking relevant proposals

## Testing

### Test Mode
- Uses separate state files in `data/test_proposal_tracking/`
- Allows testing without affecting production state
- Run with: `PYTHONPATH=. LOG_LEVEL=DEBUG python3 -m src.monitor.monitor_cosmos`

### Common Test Scenarios
1. **RPC Failure**:
   - Configure an invalid primary RPC
   - Verify fallback RPC is used
   - Check both API versions are tried

2. **API Version Fallback**:
   - Use a chain that only supports v1beta1
   - Verify v1 attempt fails and v1beta1 succeeds
   - Check proper proposal data is received

3. **Ended Proposal**:
   - Add an active proposal to the state file
   - Change its state to "passed/failed"
   - Verify end alert is sent as a thread reply

## Best Practices

1. **RPC Configuration**:
   - Use reliable RPC providers for primary endpoints
   - Configure fallback RPCs for chains with known issues
   - Monitor RPC performance and adjust timeouts if needed

2. **State Management**:
   - Don't manually modify state files in production
   - Use test mode for validation
   - Monitor state file size and clean up old entries if needed

3. **Alert Handling**:
   - Verify thread context is maintained for proposal updates
   - Monitor alert frequency and adjust polling if needed

4. **Performance Monitoring**:
   - Track RPC response times
   - Monitor fallback RPC usage
   - Watch for patterns in API version fallbacks
   - Adjust timeouts if needed 