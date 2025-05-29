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
    TALLY_API_BASE_URL: str = "https://api.tally.xyz/v1"
    
    # Slack settings
    SLACK_BOT_TOKEN: str = os.getenv("SLACK_BOT_TOKEN", "")
    SLACK_CHANNEL: str = os.getenv("SLACK_CHANNEL", "#governance-alerts")
    TEST_SLACK_CHANNEL: str = os.getenv("TEST_SLACK_CHANNEL", "#governance-alerts-test")
    
    # Monitoring settings
    POLLING_INTERVAL: int = int(os.getenv("POLLING_INTERVAL", "300"))  # 5 minutes default
    CHECK_INTERVAL: int = int(os.getenv("CHECK_INTERVAL", "60"))  # 1 minute default
    
    model_config = {
        "env_file": ".env",
        "case_sensitive": True
    }


# Create settings instance
settings = Settings()

# Ensure data directory exists
settings.DATA_DIR.mkdir(exist_ok=True) 