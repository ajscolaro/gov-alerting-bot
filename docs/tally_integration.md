# Tally Integration Documentation

## Overview

The Tally integration monitors governance proposals across multiple EVM chains, sending alerts for new proposals, proposal updates, and ended proposals. The system is designed to be efficient, handling rate limits and maintaining thread context for all proposal updates.

## Components

### 1. TallyClient (`src/integrations/tally/client.py`)

The client handles all interactions with the Tally API:

- **Proposal Fetching**: 
  - `get_active_proposals`: Fetches active proposals for a governor
  - `get_proposal`: Fetches details for a specific proposal
  - `get_proposals_by_ids`: Fetches multiple proposals in a single query
- **Error Handling**: Handles rate limiting and API errors with appropriate logging
- **Rate Limiting**: Implements rate limit handling with exponential backoff

### 2. TallyAlertHandler (`src/integrations/tally/alerts.py`)

Manages alert formatting and decision logic:

- **Alert Types**:
  - `proposal_active`: New proposals
  - `proposal_update`: Status changes (e.g., extended)
  - `proposal_ended`: Proposals that have closed

- **Alert Formatting**:
  - Each alert type has specific formatting for title, description, and action buttons
  - Thread context is maintained for proposal updates
  - Tally links are formatted based on the chain and governor address

### 3. Proposal Tracking (`src/monitor/monitor_tally.py`)

The monitor system manages proposal state and alert delivery:

#### State Management
- **Proposal State**: Tracks proposal status, thread timestamps, and alert history
- **Persistence**: State is saved to JSON files:
  - `data/proposal_tracking/tally_proposal_state.json` (production)
  - `data/test_proposal_tracking/tally_proposal_state.json` (testing)

#### Alert Processing
1. **New Proposals**:
   - Detected when a proposal isn't in the state file
   - Sends a new alert with a thread timestamp
   - Adds to tracking state

2. **Proposal Updates**:
   - Detected when a proposal's state changes (e.g., to extended)
   - Sends alert as a thread reply
   - Updates tracking state

3. **Ended Proposals**:
   - Detected when a proposal's state changes to final state (succeeded, defeated, etc.)
   - Sends alert as a thread reply
   - Removes from tracking state

### 4. Watchlist Configuration (`data/watchlists/tally_watchlist.json`)

The watchlist defines which governors to monitor:

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

Required fields:
- `name`: Display name for the project
- `description`: Brief description of the project
- `intel_label`: Determines which Slack channel receives alerts ("app" for application governance, "net" for network governance)
- `metadata.chain`: Chain name (e.g., "ethereum", "arbitrum", "base")
- `metadata.governor_address`: Tally governor contract address
- `metadata.chain_id`: Chain ID in eip155 format
- `metadata.token_address`: Governance token address
- `metadata.tally_url`: Tally governance page URL

## Error Handling

### Rate Limiting
- Implements exponential backoff for rate limit errors
- Maintains a rate limiter to prevent API throttling
- Configurable limits and retry attempts:
  - `TALLY_RATE_LIMIT`: 1 request per second
  - `RATE_LIMIT_WINDOW`: 1.0 second window
  - `MAX_RETRIES`: 3 maximum retries
  - `INITIAL_BACKOFF`: 5.0 seconds initial backoff

### API Errors
- Handles various API error types with appropriate logging
- Implements retry logic for transient errors
- Maintains state consistency during errors
- Clear error messages for debugging

## Performance Optimizations

### Batch Processing
- Proposals are grouped by governor to minimize API calls
- Multiple proposals are fetched in a single query
- Efficient proposal status tracking
- Reduced API calls by only checking relevant proposals

### Rate Limit Management
- Exponential backoff for rate limit errors
- Batch-level retry logic
- Configurable delays between requests
- Clear logging of rate limit events and retries

## Testing

### Test Mode
- Uses separate state files in `data/test_proposal_tracking/`
- Allows testing without affecting production state
- Run with: `PYTHONPATH=. LOG_LEVEL=DEBUG python3 -m src.monitor.monitor_tally`
- When running in test mode:
  - All alerts are sent to `TEST_SLACK_CHANNEL`, regardless of `intel_label`
  - Uses test state file (`data/test_proposal_tracking/tally_proposal_state.json`)
  - Runs once and exits
  - Ideal for testing new governors, alert formatting, and rate limiting
- When running through `monitor.py` (production mode):
  - Alerts are sent to `APP_SLACK_CHANNEL` or `NET_SLACK_CHANNEL` based on `intel_label`
  - Uses production state file (`data/proposal_tracking/tally_proposal_state.json`)
  - Runs continuously with configurable check interval

### Common Test Scenarios
1. **Rate Limiting**:
   - Configure aggressive rate limits
   - Verify backoff behavior
   - Check retry attempts

2. **Proposal Updates**:
   - Add an active proposal to the state file
   - Change its state to "extended"
   - Verify update alert is sent as a thread reply

3. **Ended Proposal**:
   - Add an active proposal to the state file
   - Change its state to "succeeded/defeated"
   - Verify end alert is sent as a thread reply

## Best Practices

1. **Rate Limit Configuration**:
   - Monitor rate limit occurrences
   - Adjust rate limits based on API usage
   - Configure appropriate backoff settings

2. **State Management**:
   - Don't manually modify state files in production
   - Use test mode for validation
   - Monitor state file size and clean up old entries if needed

3. **Alert Handling**:
   - Verify thread context is maintained for proposal updates
   - Monitor alert frequency and adjust polling if needed

4. **Performance Monitoring**:
   - Track API response times
   - Monitor rate limit occurrences
   - Watch for patterns in proposal updates
   - Adjust batch sizes and delays if needed 