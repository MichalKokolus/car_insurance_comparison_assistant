"""Application settings, loaded from environment / .env."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # LLM provider selection. The app runs on the stub with no key.
    anthropic_api_key: str = ""
    llm_provider: str = "stub"  # "stub" | "anthropic"
    model: str = "claude-sonnet-5"
    research_mode: str = "mock"  # "mock" | "web" (only "mock" implemented in the PoC)

    # SQLite checkpointer file — enables interrupt()/resume across HTTP requests.
    checkpoint_db: str = "checkpoints.sqlite"

    # CORS origins for the Next.js dev server (comma-separated).
    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
