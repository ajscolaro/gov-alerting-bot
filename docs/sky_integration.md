# Sky Integration Documentation

## Overview
The Sky integration monitors governance proposals from the Sky Protocol, sending alerts to Slack for new active proposals, updates, and ended proposals.

## Features
- Monitors both polls and executive votes
- Sends alerts to Slack with consistent formatting
- Thread management for updates and end states
- Comprehensive error handling and logging

## Alert Formatting
- **Title:** "Sky Protocol Executive Vote Active/Update/Ended" for executive votes
- **Title:** "Sky Protocol Poll Active/Update/Ended" for polls
- **Description:** Displays the proposal title
- **Button:** "View Proposal" linking to the proposal URL

## Thread Management
- Initial alerts create a new message in the channel
- The Slack message timestamp is stored in the state file
- Status updates (passed) and end states (executed) are sent as thread replies
- Thread replies are broadcast to the channel for visibility
- Thread context is maintained using exact Slack message timestamps
- State file format: `{ "proposal_type:proposal_id": { "status": str, "thread_ts": str, "alerted": bool, "support": float } }`

## Configuration
- Ensure the `.env` file includes the necessary Slack and API configurations.
- The `sky_watchlist.json` file should be set up with the correct project details.

## Running the Monitor
- Use the `monitor_sky.py` script to run the Sky monitor:
  ```bash
  python src/monitor/monitor_sky.py
  ```

## State Management
- State files are maintained in `data/test_proposal_tracking/sky_proposal_state.json` for testing
- Production state files are in `data/proposal_tracking/sky_proposal_state.json`
- Proposals are tracked with unique identifiers and thread context is preserved
- Thread timestamps must be exact Slack message timestamps (format: "unix_timestamp.microseconds")
- State is automatically cleaned up when proposals reach final states

## Error Handling
- Comprehensive error handling at multiple levels
- Detailed logging with timestamps and log levels
- Failed alerts are logged but don't stop the monitoring process
- Thread context errors are logged with warnings
- State file operations are atomic and backed by error handling 