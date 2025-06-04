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
   - Detected through active proposal polling
   - When fetching active proposals for a space, if a tracked proposal is not in the active list:
     - We fetch its current state directly
     - If state is "closed", send ended alert and remove from tracking
     - If proposal not found, check for deletion (see below)
   - Removes from tracking state immediately after ended alert
   - No further tracking or alerts for closed proposals

3. **Deleted Proposals**:
   - Only tracked for active proposals (closed proposals are removed from tracking)
   - Two detection mechanisms:
     1. During active proposal polling:
        - If a tracked proposal is not in active list and not found when checking state
        - Sends deletion alert and removes from tracking
     2. Through periodic existence checks:
        - Verifies all tracked active proposals still exist
        - Uses `get_proposals_by_ids` for efficient batch checking
        - Sends alert as a thread reply if an active proposal is deleted
        - Removes from tracking state
   - Handles both cases:
     - Active proposals that are deleted while being tracked
     - Active proposals that are already deleted when first checked

4. **Invalid Spaces**:
   - Detected when `check_space_exists` returns `False`
   - Sends a one-time alert with the invalid space ID
   - Marks space as alerted to prevent duplicate alerts
   - Skips future checks for this space until the watchlist is updated

#### Proposal State Management
The system uses a two-phase approach to track proposal states:

1. **Active Proposal Polling**:
   - Fetches all active proposals for each space
   - For each tracked proposal not in active list:
     - Fetches current state directly
     - If state is "closed":
       - Sends ended alert
       - Removes from tracking
     - If proposal not found:
       - Sends deletion alert
       - Removes from tracking
   - For new active proposals:
     - Sends new proposal alert
     - Adds to tracking

2. **Existence Verification**:
   - Periodic check of all tracked active proposals
   - Complements active proposal polling
   - Catches cases where proposals are deleted between polls
   - Only checks proposals that are:
     - Currently tracked
     - In active state
   - Does not check closed proposals (removed from tracking)

This dual approach ensures:
- Reliable detection of ended proposals through state changes
- Efficient detection of deleted proposals through existence checks
- No duplicate alerts for the same state change
- Proper thread context maintenance for all alerts
- Clean state management (no tracking of closed proposals)

#### Proposal Existence Checking
The system implements a robust mechanism to detect deleted proposals:

1. **Periodic Checks**:
   - Before checking for new proposals, all tracked active proposals are verified
   - Only active proposals are tracked and checked (closed proposals are removed)
   - Proposals are grouped by space for efficient batch processing
   - Uses `get_proposals_by_ids` to minimize API calls
   - Maintains rate limiting and error handling

2. **Deletion Detection**:
   - If an active proposal is not returned by the API, it is considered deleted
   - Sends a deletion alert with the original thread context
   - Removes the proposal from tracking state
   - Note: Closed proposals are not tracked and therefore not checked for deletion

3. **Error Handling**:
   - Rate limit errors trigger exponential backoff
   - Network errors are logged but don't affect other proposals
   - Failed checks for a space don't prevent checking other spaces
   - Maintains state consistency even during errors

### 4. Watchlist Configuration (`data/watchlists/snapshot_watchlist.json`)

The watchlist defines which spaces to monitor:

```json
{
  "projects": [
    {
      "name": "Project Name",
      "description": "Project Description",
      "intel_label": "app",
      "metadata": {
        "space": "space.eth",
        "snapshot_url": "https://snapshot.box/#/s:space.eth"
      }
    }
  ]
}
```

Required fields:
- `name`: Display name for the project
- `description`: Brief description of the project
- `intel_label`: Determines which Slack channel receives alerts ("app" for application governance, "net" for network governance)
- `metadata.space`: Snapshot space ID
- `metadata.snapshot_url`: Snapshot governance page URL

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