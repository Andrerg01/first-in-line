"""Application configuration loaded from environment variables via pydantic-settings.

All environment access is centralised here. Other modules import from
this module rather than calling os.environ directly.
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Runtime settings resolved from environment variables.

    All fields are read from environment variables (case-insensitive).
    An optional .env file at the project root is also loaded if present.
    """

    app_env: str = "local"
    log_level: str = "INFO"
    database_url: str = ""
    mcp_server_url: str = "http://mcp-server:9000"
    openai_api_key: str = ""
    openai_model: str = ""  # defaults to config.toml [llm] backend_model

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
