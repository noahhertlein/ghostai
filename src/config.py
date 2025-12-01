"""
Configuration management for Ghost Auto Blog Generator.
Loads settings from environment variables or .env file.
"""

import os
from dataclasses import dataclass
from pathlib import Path

# Try to load .env file if python-dotenv is available
try:
    from dotenv import load_dotenv
    
    # Load from .env file in project root
    env_path = Path(__file__).parent.parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass


@dataclass
class Config:
    """Application configuration loaded from environment variables."""
    
    # Ghost CMS Configuration
    ghost_admin_api_key: str
    ghost_url: str
    
    # Gemini AI Configuration
    gemini_api_key: str
    gemini_model: str = "gemini-3-pro-preview"
    
    # Telegram Bot Configuration
    telegram_bot_token: str
    telegram_user_id: int
    
    # Scheduling Configuration
    post_schedule_hours: int = 24  # Generate a post every N hours
    
    # Content Configuration
    topics: list = None
    
    def __post_init__(self):
        if self.topics is None:
            self.topics = [
                "Cloud Infrastructure",
                "DevOps",
                "Kubernetes",
                "Docker",
                "CI/CD Pipelines",
                "AI and Machine Learning",
                "Large Language Models",
                "Software Development",
                "Python Programming",
                "API Development",
                "Cybersecurity",
                "Cloud Security",
                "Infrastructure as Code",
                "Serverless Computing",
                "Microservices Architecture",
            ]


def load_config() -> Config:
    """Load configuration from environment variables."""
    
    # Required variables
    ghost_admin_api_key = os.environ.get('GHOST_ADMIN_API_KEY')
    ghost_url = os.environ.get('GHOST_URL')
    gemini_api_key = os.environ.get('GEMINI_API_KEY')
    telegram_bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
    telegram_user_id = os.environ.get('TELEGRAM_USER_ID')
    
    # Validate required variables
    missing = []
    if not ghost_admin_api_key:
        missing.append('GHOST_ADMIN_API_KEY')
    if not ghost_url:
        missing.append('GHOST_URL')
    if not gemini_api_key:
        missing.append('GEMINI_API_KEY')
    if not telegram_bot_token:
        missing.append('TELEGRAM_BOT_TOKEN')
    if not telegram_user_id:
        missing.append('TELEGRAM_USER_ID')
    
    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
    
    # Optional variables with defaults
    gemini_model = os.environ.get('GEMINI_MODEL', 'gemini-3-pro-preview')
    post_schedule_hours = int(os.environ.get('POST_SCHEDULE_HOURS', '24'))
    
    return Config(
        ghost_admin_api_key=ghost_admin_api_key,
        ghost_url=ghost_url.rstrip('/'),  # Remove trailing slash if present
        gemini_api_key=gemini_api_key,
        gemini_model=gemini_model,
        telegram_bot_token=telegram_bot_token,
        telegram_user_id=int(telegram_user_id),
        post_schedule_hours=post_schedule_hours,
    )


# Global config instance (lazy loaded)
_config: Config = None


def get_config() -> Config:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = load_config()
    return _config

