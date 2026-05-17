from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Указываем абсолютный путь к .env файлу
    model_config = SettingsConfigDict(
        env_file=Path(__file__).parent.parent.parent / ".env",
        env_file_encoding="utf-8", 
        extra="ignore"
    )

    database_url: str = "postgresql+asyncpg://llmchat:llmchat@localhost:5432/llmchat"
    redis_url: str = "redis://localhost:6379/0"

    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15

    github_client_id: str = ""
    github_client_secret: str = ""
    github_redirect_uri: str = "http://localhost:8000/auth/github/callback"

    llm_model_path: str = "./model.gguf"
    llm_max_tokens: int = 512
    llm_temperature: float = 0.7
    llm_context_messages: int = 10

    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"


@lru_cache
def get_settings() -> Settings:
    return Settings()