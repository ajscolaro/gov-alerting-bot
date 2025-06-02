# Snapshot Integration Documentation

## Overview

The Snapshot integration monitors governance proposals across multiple Snapshot spaces, sending alerts for new proposals, ended proposals, deleted proposals, and invalid spaces. The system is designed to be efficient, avoiding duplicate alerts and unnecessary API calls.

## Components

### 1. SnapshotClient (`src/integrations/snapshot/client.py`)

The client handles all interactions with the Snapshot API:

- **Space Validation**: Uses `check_space_exists` to verify if a space ID is valid before attempting to fetch proposals
- **Proposal Fetching**: 
  - `get_active_proposals`: Fetches active proposals for a space
  - `get_proposal`: Fetches details for a specific proposal
- **Error Handling**: Returns `None` for invalid spaces and handles rate limiting

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
   - The system sends a "space_not_detected" alert
   - The alert includes the invalid space ID and a link to verify
   - The space is marked as alerted in `admin_alerts.json`
   - Future checks for this space are skipped until the watchlist is updated

### Rate Limiting
- Implements exponential backoff for rate limit errors
- Maintains a rate limiter to prevent API throttling
- Configurable limits and retry attempts

## Testing

### Test Mode
- Uses separate state files in `data/test_proposal_tracking/`
- Allows testing without affecting production state
- Run with: `PYTHONPATH=. LOG_LEVEL=DEBUG python3 -m src.monitor.monitor_snapshot`

### Common Test Scenarios
1. **Invalid Space**:
   - Set an invalid space ID in the watchlist
   - Verify alert is sent and space is marked as alerted
   - Verify subsequent runs skip the invalid space

2. **Deleted Proposal**:
   - Add a proposal to the state file
   - Change the proposal ID to a non-existent one
   - Verify delete alert is sent as a thread reply

3. **Ended Proposal**:
   - Add an active proposal to the state file
   - Change its state to "closed"
   - Verify end alert is sent as a thread reply

## Best Practices

1. **Watchlist Management**:
   - Keep space IDs and snapshot URLs in sync
   - Use consistent naming conventions
   - Validate space IDs before adding to watchlist

2. **State Management**:
   - Don't manually modify state files in production
   - Use test mode for validation
   - Monitor state file size and clean up old entries if needed

3. **Alert Handling**:
   - Review space_not_detected alerts promptly
   - Verify thread context is maintained for proposal updates
   - Monitor alert frequency and adjust rate limits if needed 