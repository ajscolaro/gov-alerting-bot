# XRPL Integration

This document describes the XRP Ledger (XRPL) amendments integration for the Governance Alert Bot.

## Overview

The XRPL integration monitors amendments on the XRP Ledger mainnet using the [XRPScan API](https://docs.xrpscan.com/api-documentation/amendment/amendments). It tracks amendments that are supported by validators but not yet enabled, and sends alerts when amendments become active or are enabled.

## Alert Types

### Amendment Active
- **Trigger**: When a new amendment is detected that is supported by validators but not yet enabled
- **Channel**: Network governance channel (`NET_SLACK_CHANNEL`)
- **Format**: 
  - Title: "XRP Ledger Amendment Active"
  - Description: Amendment name only (e.g., "CheckCashMakesTrustLine")
  - Button: "View Amendment" linking to XRPScan

### Amendment Enabled
- **Trigger**: When a previously active amendment becomes enabled (gets an `enabled_on` timestamp)
- **Channel**: Network governance channel (`NET_SLACK_CHANNEL`)
- **Format**:
  - Title: "XRP Ledger Amendment Enabled"
  - Description: Amendment name with enabled date (e.g., "CheckCashMakesTrustLine - Enabled on 2024-01-15 14:30 UTC")
  - Button: "View Amendment" linking to XRPScan
  - **Thread**: Sent as a reply to the original "Amendment Active" alert

## Configuration

### Watchlist Structure

The XRPL watchlist is located at `data/watchlists/xrpl_watchlist.json` and follows this structure:

```json
{
  "projects": [
    {
      "name": "XRP Ledger",
      "description": "XRP Ledger Mainnet Amendments",
      "intel_label": "net",
      "metadata": {
        "api_url": "https://api.xrpscan.com",
        "amendment_url": "https://xrpscan.com/amendment"
      }
    }
  ]
}
```

### Configuration Fields

- **name**: Display name for the network
- **description**: Description of the network
- **intel_label**: Must be "net" for network governance alerts
- **metadata.api_url**: Base URL for the XRPScan API
- **metadata.amendment_url**: Base URL for amendment links on XRPScan

## API Endpoints

The integration uses the following XRPScan API endpoints:

- **GET /api/v1/amendments**: Fetch all amendments
- **GET /api/v1/amendment/{amendment_id}**: Fetch specific amendment details

## Amendment States

### Active Amendments
- `enabled: false`
- `supported: true`
- `count` and `validations` fields present
- No `enabled_on` timestamp

### Ended Amendments
- `enabled: true`
- `supported: true`
- `enabled_on` timestamp present
- May have `tx_hash` for the enabling transaction

## Monitoring Behavior

### State Tracking
- Amendments are tracked by their `amendment_id`
- State files are stored in:
  - Production: `data/proposal_tracking/xrpl_proposal_state.json`
  - Test: `data/test_proposal_tracking/xrpl_proposal_state.json`

### Alert Logic
1. **New Amendment Detection**: When an amendment is found that is supported but not enabled
2. **Status Change Detection**: When a tracked amendment becomes enabled
3. **Thread Management**: Enabled alerts are sent as replies to the original active alert
4. **Cleanup**: Enabled amendments are immediately removed from tracking after sending the "enabled" alert

### Rate Limiting
- Minimum 1 second between API requests
- 60-second timeout for API calls
- Automatic retry with backoff for network errors

## Running the Monitor

### Test Mode
```bash
python src/monitor/monitor_xrpl.py
```
- Runs once and exits
- Uses test state files
- Sends all alerts to `TEST_SLACK_CHANNEL`

### Production Mode
```bash
# Run XRPL monitor as part of the main monitoring script
python src/monitor.py --monitors xrpl

# Run XRPL monitor with other monitors
python src/monitor.py --monitors tally cosmos xrpl

# Run all monitors including XRPL
python src/monitor.py
```
- Runs continuously
- Uses production state files
- Sends alerts to `NET_SLACK_CHANNEL` based on `intel_label`
- Uses the `CHECK_INTERVAL` from your `.env` file

## Example Alerts

### Amendment Active Alert
```
XRP Ledger Amendment Active
CheckCashMakesTrustLine
[View Amendment]
```

### Amendment Enabled Alert (Thread Reply)
```
XRP Ledger Amendment Enabled
MultiSign - Enabled on 2016-06-27 23:34 UTC
[View Amendment]
```

## Error Handling

- **API Failures**: Logged but don't stop monitoring
- **Network Timeouts**: 60-second timeout with automatic retry
- **Invalid Data**: Amendments with parsing errors are skipped
- **Missing Thread Context**: Warning logged if original alert context is lost

## Integration with Google Sheets

The XRPL integration supports Google Sheets watchlist sync. Add an "XRPL" tab to your Google Sheet with these columns:

```
name | description | intel_label | api_url | amendment_url | metadata
```

Example row:
```
XRP Ledger | XRP Ledger Amendment Monitoring | net | https://api.xrpscan.com | https://xrpscan.com/amendment | {"network_type": "mainnet"}
```

**Column Details:**
- **name**: Display name for the network (e.g., "XRP Ledger")
- **description**: Description of the monitoring (e.g., "XRP Ledger Amendment Monitoring")
- **intel_label**: Either "app" or "net" to determine Slack channel routing
- **api_url**: Base URL for the XRPScan API (default: https://api.xrpscan.com)
- **amendment_url**: Base URL for amendment links (default: https://xrpscan.com/amendment)
- **metadata**: Optional JSON metadata (can be empty or contain additional config)

## Dependencies

- `aiohttp`: For async HTTP requests to XRPScan API
- `pydantic`: For data validation and parsing
- Standard library: `asyncio`, `json`, `logging`, `time`

## Rate Limits

The XRPScan API has the following rate limits:
- No specific rate limits documented
- Integration uses 1-second minimum interval between requests
- Respects HTTP 429 responses if encountered

## Troubleshooting

### Common Issues

1. **No amendments found**: Check API connectivity and response format
2. **Alerts not sending**: Verify Slack configuration and channel permissions
3. **Thread context lost**: Check state file integrity and Slack message history
4. **API timeouts**: Verify network connectivity and XRPScan API status

### Debug Mode

Enable debug logging by setting the log level to DEBUG:
```python
logging.basicConfig(level=logging.DEBUG)
```

### State File Inspection

Check the state files to verify amendment tracking:
```bash
cat data/proposal_tracking/xrpl_proposal_state.json
cat data/test_proposal_tracking/xrpl_proposal_state.json
```