from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration pulled from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: str = Field(default="dev", description="Deployment environment name")
    database_url: str = Field(
        default="postgresql+asyncpg://orbital:orbital@localhost:5432/orbitallog",
        description="SQLAlchemy connection string"
    )
    max_message_length: int = Field(default=4096, description="Maximum log message length")
    default_page_size: int = Field(default=50, ge=1, le=500)
    max_page_size: int = Field(default=500, ge=50, le=1000)

    allowed_status_codes: tuple[int, ...] = (200, 300, 400, 500)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()