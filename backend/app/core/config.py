"""Centralized configuration via environment variables (.env supported)."""
from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEFAULT_WEIGHTS: dict[str, float] = {
    "value": 25,
    "failure_frequency": 10,
    "customer_value": 20,
    "historical_success": 10,
    "probability": 25,
    "recency": 10,
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "RecoveryAI"
    environment: str = "local"
    debug: bool = True

    database_url: str = "sqlite:///./recovery_ai.db"

    secret_key: str = "change-me-in-production-with-at-least-32-byte-key"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 480
    demo_user_email: str = "merchant@recovery.ai"
    demo_user_password: str = "demo1234"

    cors_origins: str = (
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8080"
    )

    webhook_secret: str = "demo-webhook-secret"
    allow_unsigned_webhooks: bool = False

    # Demo hosting: seed a fresh (ephemeral) database on first boot.
    seed_on_startup: bool = False
    seed_customers: int = 5000
    seed_transactions: int = 20000

    llm_provider: str = "mock"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    groq_api_key: str = ""
    groq_model: str = "llama-3.1-8b-instant"

    rate_limit_per_minute: int = 600

    scoring_weights_json: str = json.dumps(_DEFAULT_WEIGHTS)

    # Baseline (rule-based dunning) assumed success probability by root cause.
    baseline_success_probabilities_json: str = json.dumps(
        {
            "PAYMENT_METHOD_ISSUE": 0.12,
            "BANK_OR_NETWORK": 0.30,
            "FRAUD_OR_RISK": 0.05,
            "CUSTOMER_BEHAVIOR": 0.20,
            "SYSTEM": 0.25,
        }
    )

    @model_validator(mode="after")
    def validate_production_settings(self) -> "Settings":
        if self.environment.lower() in {"local", "dev", "development", "test", "testing"}:
            return self
        if self.secret_key.startswith("change-me") or len(self.secret_key) < 32:
            raise ValueError("SECRET_KEY must be a strong non-placeholder value outside local development")
        if self.allow_unsigned_webhooks:
            raise ValueError("ALLOW_UNSIGNED_WEBHOOKS must be false outside local development")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def scoring_weights(self) -> dict[str, float]:
        try:
            parsed: dict[str, Any] = json.loads(self.scoring_weights_json)
            merged = dict(_DEFAULT_WEIGHTS)
            merged.update({k: float(v) for k, v in parsed.items()})
            return merged
        except (json.JSONDecodeError, TypeError, ValueError):
            return dict(_DEFAULT_WEIGHTS)

    @property
    def baseline_success_probabilities(self) -> dict[str, float]:
        try:
            parsed: dict[str, Any] = json.loads(self.baseline_success_probabilities_json)
            return {k: float(v) for k, v in parsed.items()}
        except (json.JSONDecodeError, TypeError, ValueError):
            return {
                "PAYMENT_METHOD_ISSUE": 0.12,
                "BANK_OR_NETWORK": 0.30,
                "FRAUD_OR_RISK": 0.05,
                "CUSTOMER_BEHAVIOR": 0.20,
                "SYSTEM": 0.25,
            }


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
