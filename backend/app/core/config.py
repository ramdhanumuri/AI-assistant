"""Application configuration.

Settings are read from environment variables (and an optional `.env` file)
so that the same image runs unchanged across development and production.
Later modules extend this file rather than introducing a second config path.
"""

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Application
    APP_NAME: str = "AURELIS Intelligence API"
    APP_ENV: str = "development"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"
    CORS_ORIGINS: list[str] = [
        "http://localhost:12000",
        "http://127.0.0.1:12000",
    ]

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 12001

    # Database
    DATABASE_URL: str = "sqlite:///./aurelis.db"

    # Model layer (seam resolved in MODULE 6)
    AI_PROVIDER: str = "simulator"
    AI_MODEL: str = ""
    AI_PROVIDER_API_KEY: str = ""

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @property
    def is_sqlite(self) -> bool:
        return self.DATABASE_URL.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    """Cached accessor so config is parsed once per process."""
    return Settings()


settings = get_settings()
