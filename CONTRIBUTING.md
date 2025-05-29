# Contributing to Governance Alert Bot

This document explains the core components of the bot and how they work together.

## Core Files

### Main Monitoring Script
- `src/monitor.py`: Main entry point that orchestrates monitoring across all platforms

### Common Components
- `src/common/models.py`: Shared data models used across the application
- `src/common/config.py`: Configuration handling and environment variables
- `src/common/alerts/base.py`: Base alert functionality and interfaces
- `src/common/alerts/slack.py`: Slack-specific alert implementation

### Platform Integrations
Each platform integration follows a similar structure:

#### Tally Integration
- `src/integrations/tally/client.py`: Tally API client
- `src/integrations/tally/alerts.py`: Tally-specific alert formatting
- `src/integrations/tally/models.py`: Tally-specific data models

#### Cosmos Integration
- `src/integrations/cosmos/client.py`: Cosmos REST API client
- `src/integrations/cosmos/alerts.py`: Cosmos-specific alert formatting
- `src/integrations/cosmos/models.py`: Cosmos-specific data models

## How It Works

1. **Initialization**
   - The bot loads configuration from environment variables
   - Initializes the Slack alert sender
   - Creates platform-specific clients and alert handlers
   - Loads the watchlist configuration

2. **Monitoring Loop**
   - Each platform runs in its own monitoring loop
   - Proposals are fetched from platform-specific APIs
   - State is tracked in `proposal_state.json`
   - Alerts are sent via Slack when changes are detected

3. **Alert Flow**
   - New proposals trigger initial alerts
   - Status changes are sent as thread replies
   - Final states remove proposals from tracking

## Adding New Platforms

To add a new platform:

1. Create a new directory in `src/integrations/`
2. Implement the required components:
   - Client for API interaction
   - Alert handler for message formatting
   - Data models for the platform
3. Add the platform to the monitoring loop in `monitor.py`
4. Update the watchlist configuration format

## Development Setup

1. Clone the repository
2. Create a virtual environment
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   ```
4. Create necessary data files:
   - `data/proposal_state.json`
   - `data/tally_watchlist.json`
   - `data/cosmos_watchlist.json`
5. Set up environment variables in `.env`

## Testing

Run the test suite:
```bash
pytest tests/ -v
```

## Code Style

- Follow PEP 8 guidelines
- Use type hints
- Document public functions and classes
- Write tests for new functionality 