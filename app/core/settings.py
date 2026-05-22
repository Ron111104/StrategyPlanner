"""Application settings loaded from environment variables."""
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )

    APP_NAME: str = "StrategyPlanner"
    APP_ENV: Literal["development", "staging", "production"] = "development"
    APP_DEBUG: bool = True
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000

    QH_API_BASE_URL: str = "https://api.example.com"
    QH_API_KEY: str = ""
    QH_API_TIMEOUT: int = 30

    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: Literal["json", "console"] = "json"

    CACHE_TTL_SECONDS: int = 300
    MAX_BARS_PER_REQUEST: int = 5000

    @property
    def base_dir(self) -> Path:
        return Path(__file__).resolve().parent.parent

    @property
    def config_dir(self) -> Path:
        return self.base_dir / "config"

    @property
    def templates_dir(self) -> Path:
        return self.base_dir / "templates"

    @property
    def static_dir(self) -> Path:
        return self.base_dir / "static"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
