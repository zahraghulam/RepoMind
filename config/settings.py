"""
config/settings.py

Pydantic BaseSettings for RepoMind.

Supports both Groq (primary, free) and OpenAI (fallback) backends.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ─────────────────────────────────────────────────────────────
    # LLM - Groq
    # ─────────────────────────────────────────────────────────────
    groq_api_key: str | None = None
    llm_model: str = "llama-3.3-70b-versatile"

    # ─────────────────────────────────────────────────────────────
    # LLM - OpenAI
    # ─────────────────────────────────────────────────────────────
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o"

    # ─────────────────────────────────────────────────────────────
    # Plan
    # ─────────────────────────────────────────────────────────────
    max_plan_steps: int = 10

    # ─────────────────────────────────────────────────────────────
    # GitHub
    # ─────────────────────────────────────────────────────────────
    github_token: str | None = None
    github_username: str | None = None

    # ─────────────────────────────────────────────────────────────
    # App
    # ─────────────────────────────────────────────────────────────
    app_env: str = "development"
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_settings(self) -> Settings:
        """
        Validate required settings after loading environment variables.
        """

        if not self.groq_api_key and not self.openai_api_key:
            raise ValueError(
                "At least one LLM API key must be provided " "(GROQ_API_KEY or OPENAI_API_KEY)."
            )

        if not self.github_token:
            raise ValueError("GITHUB_TOKEN is required.")

        if not self.github_username:
            raise ValueError("GITHUB_USERNAME is required.")

        return self

    @property
    def active_llm_model(self) -> str:
        if self.openai_api_key:
            return self.openai_model
        return self.llm_model

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
