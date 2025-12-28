"""
Configuration settings for Mugen Claude orchestrator.
"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings."""

    # Claude CLI Configuration
    model: str = "sonnet"  # Can be "sonnet", "opus", or "haiku"
    max_tokens: int = 4096  # Not used by CLI, for reference only

    # Agent Configuration
    agent_timeout: float = 120.0
    max_concurrent_agents: int = 5

    # File Locking
    file_lock_timeout: float = 10.0

    # Logging
    log_level: str = "INFO"
    log_file: Optional[str] = None

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
