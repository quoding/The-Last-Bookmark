from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/tainai"

    llm_api_key: str = ""
    llm_model: str = "gpt-5.6-luna"

    image_api_key: str = ""
    image_model: str = "gpt-image-2"
    image_quality: str = "low"
    image_size: str = "1024x1536"

    invite_code_hashes: str = ""  # "code_id:sha256hash,code_id:sha256hash"
    auth_secret: str = "dev-secret-change-me"

    image_budget_sessions: int = 100
    storage_path: str = "./storage"


@lru_cache
def get_settings() -> Settings:
    return Settings()
