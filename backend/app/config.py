"""Application configuration loaded from environment variables.

All environment access is centralised here. Other modules import from
this module rather than calling os.environ directly.
"""
import os


class Settings:
    """Runtime settings resolved from environment variables."""

    app_env: str = os.environ.get("APP_ENV", "local")
    log_level: str = os.environ.get("LOG_LEVEL", "INFO")
    database_url: str = os.environ.get("DATABASE_URL", "")
    mcp_server_url: str = os.environ.get("MCP_SERVER_URL", "")


settings = Settings()
