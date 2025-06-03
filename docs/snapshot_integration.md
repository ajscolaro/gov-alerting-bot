# Snapshot Integration Documentation

## Overview

The Snapshot integration monitors governance proposals across multiple Snapshot spaces, sending alerts for new proposals, ended proposals, deleted proposals, and invalid spaces. The system is designed to be efficient, avoiding duplicate alerts and unnecessary API calls.

## Components

### 1. SnapshotClient (`src/integrations/snapshot/client.py`)

The client handles all interactions with the Snapshot API:

- **Space Validation**: Uses `validate_space` to explicitly check if a space ID is valid
  - Returns `True` if space exists
  - Returns `False` if space explicitly doesn't exist
  - Returns `None` if an error occurred during validation
- **Proposal Fetching**: 
  - `get_active_proposals`: Fetches active proposals for a space, returns:
    - `None` if an error occurred during fetching
    - `[]` if space exists but has no active proposals
    - List of proposals if space exists and has active proposals
  - `get_proposal`: Fetches details for a specific proposal
  - `get_proposals_by_ids`: Fetches multiple proposals in a single query for efficient batch processing
- **Error Handling**: Handles rate limiting and GraphQL errors with appropriate logging

### 2. SnapshotAlertHandler (`src/integrations/snapshot/alerts.py`)

Manages alert formatting and decision logic:

- **Alert Types**:
  - `proposal_active`: New proposals
  - `proposal_ended`: Proposals that have closed
  - `proposal_deleted`: Proposals that have been deleted
  - `space_not_detected`: Invalid space IDs

- **Alert Formatting**:
  - Each alert type has specific formatting for title, description, and action buttons
  - Thread context is maintained for proposal updates
  - Space not detected alerts include the invalid space ID for easy identification

### 3. Proposal Tracking (`src/monitor/monitor_snapshot.py`)

The monitor system manages proposal state and alert delivery:

#### State Management
- **Proposal State**: Tracks proposal status, thread timestamps, and alert history
- **Space Alerts**: Maintains a record of spaces that have triggered invalid space alerts
- **Persistence**: State is saved to JSON files:
  - `data/proposal_tracking/snapshot_proposal_state.json` (production)
  - `data/test_proposal_tracking/snapshot_proposal_state.json` (testing)

#### Alert Processing
1. **New Proposals**:
   - Detected when a proposal isn't in the state file
   - Sends a new alert with a thread timestamp
   - Adds to tracking state

2. **Ended Proposals**:
   - Detected when a proposal's state changes from "active" to "closed"
   - Sends alert as a thread reply
   - Removes from tracking state

3. **Deleted Proposals**:
   - Detected when a proposal can't be found
   - Sends alert as a thread reply
   - Removes from tracking state

4. **Invalid Spaces**:
   - Detected when `check_space_exists` returns `False`
   - Sends a one-time alert with the invalid space ID
   - Marks space as alerted to prevent duplicate alerts
   - Skips future checks for this space until the watchlist is updated

### 4. Watchlist Configuration (`data/watchlists/snapshot_watchlist.json`)

The watchlist defines which spaces to monitor:

```json
{
  "projects": [
    {
      "name": "Project Name",
      "description": "Project Description",
      "intel_label": "app|net",
      "metadata": {
        "space": "space.eth",
        "snapshot_url": "https://snapshot.box/#/s:space.eth"
      }
    }
  ]
}
```

## Error Handling

### Invalid Spaces
1. When a space ID is invalid:
   - The system first validates the space using `validate_space`
   - Admin alerts are ONLY triggered when `validate_space` returns `False` (space explicitly doesn't exist)
   - Errors during validation (`None` return) are logged but do not trigger alerts
   - The alert includes the invalid space ID and a link to verify
   - The space is marked as alerted in `admin_alerts.json`
   - Future checks for this space are skipped until the watchlist is updated

2. Error Handling:
   - Network errors or API failures during space validation do not trigger admin alerts
   - Errors during proposal fetching are logged but do not trigger alerts
   - Rate limit errors are handled with exponential backoff
   - All errors are logged with appropriate context for debugging

### Rate Limiting
- Implements exponential backoff for rate limit errors
- Maintains a rate limiter to prevent API throttling
- Configurable limits and retry attempts:
  - `SNAPSHOT_RATE_LIMIT`: 1 request per second
  - `RATE_LIMIT_WINDOW`: 1.0 second window
  - `MAX_RETRIES`: 3 maximum retries
  - `INITIAL_BACKOFF`: 5.0 seconds initial backoff
  - `BATCH_SIZE`: 5 spaces per batch
- Batch processing of spaces to minimize API calls
- Delays between batches to avoid rate limits

## Performance Optimizations

### Batch Processing
- Proposals are grouped by space to minimize API calls
- Spaces are processed in batches of 5 to manage rate limits
- Multiple proposals are fetched in a single query using `get_proposals_by_ids`
- Delays between batches (2 seconds) to prevent rate limiting

### Space Checking
- Space existence is checked as part of proposal fetching
- No separate API calls for space validation
- Invalid spaces are tracked to avoid repeated checks
- Spaces with no active proposals are distinguished from non-existent spaces

### Rate Limit Management
- Exponential backoff for rate limit errors
- Batch-level retry logic
- Configurable delays between requests
- Clear logging of rate limit events and retries

## Testing

### Test Mode
- Uses separate state files in `data/test_proposal_tracking/`
- Allows testing without affecting production state
- Run with: `PYTHONPATH=. LOG_LEVEL=DEBUG python3 -m src.monitor.monitor_snapshot`

### Common Test Scenarios
1. **Invalid Space**:
   - Set an invalid space ID in the watchlist
   - Verify alert is ONLY sent when `validate_space` returns `False`
   - Verify no alert is sent for validation errors (`None` return)
   - Verify space is marked as alerted in `admin_alerts.json`
   - Verify subsequent runs skip the invalid space

2. **Space Validation Errors**:
   - Simulate network errors during space validation
   - Verify no admin alert is sent
   - Verify error is logged appropriately
   - Verify monitoring continues for other spaces

## Best Practices

1. **Watchlist Management**:
   - Keep space IDs and snapshot URLs in sync
   - Use consistent naming conventions
   - Validate space IDs before adding to watchlist
   - Monitor admin alerts for invalid spaces
   - Update watchlist promptly when invalid spaces are detected

2. **State Management**:
   - Don't manually modify state files in production
   - Use test mode for validation
   - Monitor state file size and clean up old entries if needed
   - Review `admin_alerts.json` periodically to identify stale invalid spaces

3. **Alert Handling**:
   - Review space_not_detected alerts promptly
   - Verify alerts are only triggered for explicitly invalid spaces
   - Monitor error logs for validation failures
   - Verify thread context is maintained for proposal updates
   - Monitor alert frequency and adjust rate limits if needed

4. **Performance Monitoring**:
   - Monitor rate limit occurrences
   - Track batch processing times
   - Watch for patterns in space validation failures
   - Monitor error rates for space validation
   - Adjust batch sizes and delays if needed 