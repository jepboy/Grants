from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    anthropic_api_key: str = Field(default="", validation_alias="ANTHROPIC_API_KEY")
    voyage_api_key: str = Field(default="", validation_alias="VOYAGE_API_KEY")
    openai_api_key: str = Field(default="", validation_alias="OPENAI_API_KEY")
    propublica_api_key: str = Field(default="", validation_alias="PROPUBLICA_API_KEY")

    database_url: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/grants",
        validation_alias="DATABASE_URL",
    )

    drafter_model: str = Field(default="claude-opus-4-7", validation_alias="DRAFTER_MODEL")
    verifier_model: str = Field(default="claude-opus-4-7", validation_alias="VERIFIER_MODEL")
    subtask_model: str = Field(default="claude-sonnet-4-6", validation_alias="SUBTASK_MODEL")

    embedding_provider: str = Field(default="voyage", validation_alias="EMBEDDING_PROVIDER")
    embedding_model: str = Field(default="voyage-3", validation_alias="EMBEDDING_MODEL")

    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")


settings = Settings()
