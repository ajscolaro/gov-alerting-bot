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

## Configuration
- Ensure the `.env` file includes the necessary Slack and API configurations.
- The `sky_watchlist.json` file should be set up with the correct project details.

## Running the Monitor
- Use the `monitor_sky.py` script to run the Sky monitor:
  ```bash
  python src/monitor/monitor_sky.py
  ```

## State Management
- State files are maintained in `data/test_proposal_tracking/sky_proposal_state.json`.
- Proposals are tracked with unique identifiers and thread context is preserved.

## Error Handling
- Comprehensive error handling at multiple levels
- Detailed logging with timestamps and log levels
- Failed alerts are logged but don't stop the monitoring process 