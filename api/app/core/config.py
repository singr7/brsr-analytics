from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    log_level: str = "INFO"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    database_url: str = "postgresql+asyncpg://brsrlens:brsrlens@postgres:5432/brsrlens"
    redis_url: str = "redis://redis:6379/0"
    llm_provider: str = "fake"
    llm_api_key: str | None = None
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4.1-mini"
    llm_fixture_case: str = "default"
    llm_network_enabled: bool = Field(default=False)

    @property
    def llm_config_present(self) -> bool:
        return self.llm_provider == "fake" or bool(self.llm_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
