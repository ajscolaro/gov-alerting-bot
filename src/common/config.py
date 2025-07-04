import os
from pathlib import Path
from typing import Dict, List

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

# Load environment variables from .env file
load_dotenv()


class Settings(BaseSettings):
    """Application settings."""
    # Base paths
    BASE_DIR: Path = Path(__file__).parent.parent.parent
    DATA_DIR: Path = BASE_DIR / "data"
    
    # API Keys and endpoints
    TALLY_API_KEY: str = os.getenv("TALLY_API_KEY", "")
    TEST_TALLY_API_KEY: str = os.getenv("TEST_TALLY_API_KEY", "")  # Test API key for test mode
    TALLY_API_BASE_URL: str = "https://api.tally.xyz/v1"
    
    # Slack settings
    SLACK_BOT_TOKEN: str = os.getenv("SLACK_BOT_TOKEN", "")
    SLACK_CHANNEL: str = os.getenv("SLACK_CHANNEL", "#govbot-beta")
    APP_SLACK_CHANNEL: str = os.getenv("APP_SLACK_CHANNEL", "")  # Channel for app alerts
    NET_SLACK_CHANNEL: str = os.getenv("NET_SLACK_CHANNEL", "")  # Channel for network alerts
    TEST_SLACK_CHANNEL: str = os.getenv("TEST_SLACK_CHANNEL", "#govbot-testing")
    
    # Monitoring settings
    POLLING_INTERVAL: int = int(os.getenv("POLLING_INTERVAL", "300"))  # 5 minutes default
    CHECK_INTERVAL: int = int(os.getenv("CHECK_INTERVAL", "60"))  # 1 minute default
    TEST_CHECK_INTERVAL: int = int(os.getenv("TEST_CHECK_INTERVAL", "60"))  # 1 minute default for test mode
    
    model_config = {
        "env_file": ".env",
        "case_sensitive": True,
        "extra": "allow"  # Allow extra fields in environment variables
    }


# Create settings instance
settings = Settings()

# Ensure data directory exists
settings.DATA_DIR.mkdir(exist_ok=True) 