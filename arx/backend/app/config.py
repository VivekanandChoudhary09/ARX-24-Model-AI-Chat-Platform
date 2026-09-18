from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    MONGODB_URI: str = "mongodb://localhost:27017/arx"
    MONGODB_DB: str = "arx"
    CHROMA_PATH: str = "./chroma_data"
    EMBEDDING_MODEL: str = "BAAI/bge-small-en-v1.5"
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_MINUTES: int = 60
    INTERNAL_API_KEY: str
    ALLOWED_ORIGINS: str = "http://localhost:3000"
    REDIS_URL: str = ""
    DEFAULT_MONTHLY_TOKEN_QUOTA: int = 500000
    DEFAULT_IP_HOURLY_REQUESTS: int = 120

    @property
    def allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
