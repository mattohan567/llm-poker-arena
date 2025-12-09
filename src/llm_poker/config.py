"""Configuration management for LLM Poker Arena."""

import os

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # LLM API Keys
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    google_api_key: str = Field(default="", alias="GOOGLE_API_KEY")
    groq_api_key: str = Field(default="", alias="GROQ_API_KEY")
    mistral_api_key: str = Field(default="", alias="MISTRAL_API_KEY")
    deepseek_api_key: str = Field(default="", alias="DEEPSEEK_API_KEY")

    # Supabase
    supabase_url: str = Field(default="", alias="SUPABASE_URL")
    supabase_key: str = Field(default="", alias="SUPABASE_KEY")

    # Game Settings
    default_starting_stack: int = Field(default=1_500_000, alias="DEFAULT_STARTING_STACK")
    default_small_blind: int = Field(default=5_000, alias="DEFAULT_SMALL_BLIND")
    default_big_blind: int = Field(default=10_000, alias="DEFAULT_BIG_BLIND")

    # LLM Settings
    llm_timeout: int = Field(default=30, alias="LLM_TIMEOUT")
    llm_retries: int = Field(default=3, alias="LLM_RETRIES")
    llm_temperature: float = Field(default=0.7, alias="LLM_TEMPERATURE")

    # Equity Calculator
    equity_sample_count: int = Field(default=1000, alias="EQUITY_SAMPLE_COUNT")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


# Default models for tournaments
DEFAULT_MODELS = [
    "openai/gpt-4o",
    "anthropic/claude-sonnet-4-20250514",
    "gemini/gemini-1.5-pro",
    "groq/llama-3.1-70b-versatile",
    "mistral/mistral-large-latest",
    "deepseek/deepseek-chat",
]


# Singleton settings instance
settings = Settings()

# Export API keys to environment for litellm compatibility
# LiteLLM reads API keys from os.environ, not from pydantic settings
if settings.openai_api_key:
    os.environ.setdefault("OPENAI_API_KEY", settings.openai_api_key)
if settings.anthropic_api_key:
    os.environ.setdefault("ANTHROPIC_API_KEY", settings.anthropic_api_key)
if settings.google_api_key:
    os.environ.setdefault("GOOGLE_API_KEY", settings.google_api_key)
if settings.groq_api_key:
    os.environ.setdefault("GROQ_API_KEY", settings.groq_api_key)
if settings.mistral_api_key:
    os.environ.setdefault("MISTRAL_API_KEY", settings.mistral_api_key)
if settings.deepseek_api_key:
    os.environ.setdefault("DEEPSEEK_API_KEY", settings.deepseek_api_key)
