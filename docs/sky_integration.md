# Sky Integration Documentation

## Overview
The Sky integration monitors governance proposals from the Sky Protocol, sending alerts to Slack for new active proposals, updates, and ended proposals.

## Features
- Monitors both polls and executive votes
- Sends alerts to Slack with consistent formatting
- Thread management for updates and end states
- Comprehensive error handling and logging
- Automatic cleanup of completed proposals
- Timezone-aware datetime handling for accurate status tracking

## Alert Types and Status Transitions
### Polls
- **Active**: Initial state when a poll is created
- **Ended**: Final state when voting period concludes (determined by comparing end_time with current time)
- Alert transitions: Active → Ended
- Status determination:
  - Uses timezone-aware datetime comparison
  - Compares poll's end_time (UTC) with current time
  - Automatically transitions to "ended" when end_time is reached

### Executive Votes
- **Active**: Initial state when vote is created
- **Passed**: Intermediate state when vote receives sufficient support
- **Executed**: Final state when vote is executed on-chain
- Alert transitions: Active → Passed → Executed
- Status determination:
  - Based on spell data and active flag
  - Uses hasBeenCast for executed status
  - Uses datePassed or active flag for passed status

## Alert Formatting
- **Title Format:**
  - Executive Votes: "{Project Name} Executive Vote {Status}"
  - Polls: "{Project Name} Poll {Status}"
- **Status Values:** Active, Update, Ended/Executed
- **Description:** Displays the proposal title
- **Button:** "View Proposal" linking to the proposal URL

## Thread Management
- Initial alerts create a new message in the channel
- The Slack message timestamp is stored in the state file
- Status updates and end states are sent as thread replies
- Thread replies are broadcast to the channel for visibility
- Thread context is maintained using exact Slack message timestamps
- State file format: `{ "proposal_type:proposal_id": { "status": str, "thread_ts": str, "alerted": bool, "support": float } }`

## Configuration
- Required environment variables in `.env`:
  - `SLACK_BOT_TOKEN`: Bot token for Slack integration
  - `SLACK_CHANNEL`: Production channel for alerts
  - `TEST_SLACK_CHANNEL`: Channel for test alerts
  - `CHECK_INTERVAL`: Seconds between monitoring checks (default: 60)
- The `sky_watchlist.json` file must include:
  - Project name
  - Required metadata fields: `poll_url` and `executive_url`

## Running the Monitor

### Production Mode
```bash
# Run through monitor.py (continuous, production mode)
python src/monitor.py --monitors sky
```
- Uses production state file (`data/proposal_tracking/sky_proposal_state.json`)
- Sends alerts to production channel
- Runs continuously with configurable check interval
- Can be run alongside other monitors (Tally, Cosmos, Snapshot)

### Test Mode
```bash
# Run directly (test mode, runs once and exits)
python src/monitor/monitor_sky.py
```
- Uses test state file (`data/test_proposal_tracking/sky_proposal_state.json`)
- Sends alerts to test channel
- Runs once and exits
- Good for testing and debugging

## State Management
- **Production Environment:**
  - State file: `data/proposal_tracking/sky_proposal_state.json`
  - Used when running through monitor.py
  - Continuous monitoring with configurable check interval
- **Test Environment:**
  - State file: `data/test_proposal_tracking/sky_proposal_state.json`
  - Used when running monitor_sky.py directly
  - Single run for testing and debugging
- Features:
  - Unique proposal tracking with type:id keys (e.g., "poll:123", "executive:456")
  - Thread context preservation
  - Support percentage tracking for executive votes (stored but not displayed)
  - Automatic cleanup of completed proposals
  - Atomic state file operations
  - Separate handling for polls and executive votes

## Error Handling
- Comprehensive error handling at multiple levels:
  - API communication errors
  - State file operations
  - Alert sending failures
  - Thread context management
  - Timezone and datetime parsing
- Detailed logging with timestamps and log levels
- Failed alerts are logged but don't stop the monitoring process
- Thread context errors are logged with warnings
- State file operations are atomic and backed by error handling
- Automatic retry for transient errors
- Graceful handling of network issues

## Best Practices
1. **Timezone Handling:**
   - All datetime comparisons use timezone-aware objects
   - API timestamps (UTC) are properly converted
   - Current time is converted to local timezone for comparison

2. **State Management:**
   - Don't manually modify state files
   - Use test mode for validation
   - Monitor state file size and clean up old entries if needed

3. **Alert Handling:**
   - Verify thread context is maintained for proposal updates
   - Monitor alert frequency and adjust polling if needed
   - Check both polls and executive votes are properly tracked

4. **Performance Monitoring:**
   - Track API response times
   - Monitor status transition accuracy
   - Watch for patterns in proposal updates
   - Verify timezone handling is working correctly 