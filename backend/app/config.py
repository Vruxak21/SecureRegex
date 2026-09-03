"""
Application settings — loaded from environment variables with sensible defaults.

All configuration is centralised here so every module imports from one place.
Uses pydantic-settings for automatic env-var parsing and validation.
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the SecureRegex backend."""

    model_config = SettingsConfigDict(
        env_prefix="SECUREREGEX_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── API ──────────────────────────────────────────────────────────────────
    app_name: str = Field(default="SecureRegex", description="Human-readable app name")
    app_version: str = Field(default="0.1.0", description="Semver string")
    debug: bool = Field(default=False, description="Enable debug mode")

    # ── CORS ─────────────────────────────────────────────────────────────────
    # Comma-separated list of allowed origins for the frontend dev server.
    cors_origins: list[str] = Field(
        default=["http://localhost:5173", "http://127.0.0.1:5173"],
        description="List of CORS-allowed origins",
    )

    # ── Regex engine limits ──────────────────────────────────────────────────
    max_regex_length: int = Field(
        default=1_000,
        ge=1,
        le=10_000,
        description="Maximum number of characters in a submitted regex pattern",
    )
    max_input_length: int = Field(
        default=10_000,
        ge=1,
        le=100_000,
        description="Maximum number of characters in a test input string",
    )
    max_nfa_states: int = Field(
        default=5_000,
        ge=10,
        le=50_000,
        description="Maximum NFA states before aborting construction (safety cap)",
    )
    max_dfa_states: int = Field(
        default=2_000,
        ge=10,
        le=20_000,
        description="Maximum DFA states before aborting subset construction",
    )
    max_computation_steps: int = Field(
        default=1_000_000,
        ge=1_000,
        description="Maximum simulation steps before declaring a timeout",
    )


# Module-level singleton — import this from everywhere else.
settings = Settings()
