"""
app/core/config.py  — Pydantic Settings with env + optional YAML overlay.

All secrets come from environment variables ONLY.
Non-secret structured config may come from a YAML file pointed to by
PRAMAAN_CONFIG_FILE (absolute path).
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, Literal

import yaml
from pydantic import AnyUrl, Field, PostgresDsn, RedisDsn, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DB_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    host: str = "localhost"
    port: int = 5432
    name: str = "pramaan"
    user: str = "pramaan"
    password: SecretStr = SecretStr("pramaan")
    pool_size: int = 10
    max_overflow: int = 20
    pool_pre_ping: bool = True
    async_url_override: str = ""

    @property
    def async_url(self) -> str:
        if self.async_url_override:
            return self.async_url_override
        pw = self.password.get_secret_value()
        return f"postgresql+asyncpg://{self.user}:{pw}@{self.host}:{self.port}/{self.name}"


class RedisSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="REDIS_", extra="ignore")

    host: str = "localhost"
    port: int = 6379
    password: SecretStr = SecretStr("")
    db: int = 0
    stream_max_len: int = 100_000      # per stream approximate max entries

    @property
    def url(self) -> str:
        pw = self.password.get_secret_value()
        auth = f":{pw}@" if pw else "@"
        return f"redis://{auth}{self.host}:{self.port}/{self.db}"


class S3Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="S3_", extra="ignore")

    endpoint_url: str = "http://localhost:9000"
    access_key_id: SecretStr = SecretStr("minioadmin")
    secret_access_key: SecretStr = SecretStr("minioadmin")
    bucket_evidence: str = "pramaan-evidence"
    region: str = "ap-south-1"
    presign_ttl_seconds: int = 900          # 15 min
    evidence_max_bytes: int = 5 * 1024 * 1024   # 5 MB


class AuthSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AUTH_", extra="ignore")

    # OIDC / JWT
    oidc_issuer: str = "http://localhost:8000/dev-oidc"
    jwks_url: str = ""                      # empty → use local dev issuer
    jwt_algorithm: str = "RS256"
    jwt_audience: str = "pramaan-api"
    jwt_clock_skew_seconds: int = 30

    # Local dev issuer (used when jwks_url is empty)
    dev_jwt_secret: SecretStr = SecretStr("dev-only-secret-change-in-prod")

    # Device auth
    device_enrollment_token_ttl_seconds: int = 3600
    device_clock_skew_window_seconds: int = 300   # ±5 min
    device_observation_buffer_window_seconds: int = 60  # out-of-order buffer

    @model_validator(mode="after")
    def _set_jwks_default(self) -> "AuthSettings":
        if not self.jwks_url:
            self.jwks_url = f"{self.oidc_issuer}/.well-known/jwks.json"
        return self


class ObservabilitySettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="OTEL_", extra="ignore")

    otlp_endpoint: str = ""
    service_name: str = "pramaan-backend"
    log_level: str = "INFO"
    metrics_prefix: str = "pramaan"


class RateLimitSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RATELIMIT_", extra="ignore")

    ingest_per_device_rpm: int = 120        # observations per minute per device
    api_per_user_rpm: int = 600
    evidence_presign_rpm: int = 30


class Settings(BaseSettings):
    """Top-level settings aggregator. Loads from environment, then optional YAML overlay."""

    model_config = SettingsConfigDict(
        env_prefix="PRAMAAN_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False
    api_version: str = "v1"
    cors_origins: list[str] = ["http://localhost:3000"]
    request_id_header: str = "X-Request-ID"

    # Sub-settings (read directly from env with their own prefixes)
    db: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    s3: S3Settings = Field(default_factory=S3Settings)
    auth: AuthSettings = Field(default_factory=AuthSettings)
    otel: ObservabilitySettings = Field(default_factory=ObservabilitySettings)
    rate_limit: RateLimitSettings = Field(default_factory=RateLimitSettings)

    # Reconciliation defaults (override via threshold_profile table)
    default_t_green: float = Field(default=0.80, description="Lower bound of GREEN attendance ratio")
    default_t_amber: float = Field(default=0.50, description="Lower bound of AMBER attendance ratio")
    default_repeat_n: int = Field(default=2, description="Sessions below t_amber to trigger RED")

    # Perceptual hash near-duplicate threshold (Hamming distance)
    phash_hamming_threshold: int = Field(default=10, description="Hamming distance ≤ this → near-duplicate")

    # Feed health
    min_feed_health_fraction: float = Field(
        default=0.50, description="Fraction of session window with healthy feed required for reconciliation"
    )

    # Evidence retention
    evidence_retention_days: int = Field(default=90, description="Days before evidence S3 objects are deleted")
    observation_retention_days: int = Field(default=365, description="Days before raw observations are dropped")

    @field_validator("default_t_green", "default_t_amber", mode="before")
    @classmethod
    def _validate_ratio(cls, v: Any) -> float:
        fv = float(v)
        if not 0.0 <= fv <= 1.0:
            msg = "Threshold must be in [0, 1]"
            raise ValueError(msg)
        return fv

    @model_validator(mode="after")
    def _load_yaml_overlay(self) -> "Settings":
        config_file = os.environ.get("PRAMAAN_CONFIG_FILE")
        if config_file:
            path = Path(config_file)
            if path.exists():
                with path.open() as fh:
                    overlay = yaml.safe_load(fh) or {}
                for k, v in overlay.items():
                    if hasattr(self, k):
                        setattr(self, k, v)
        return self

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached Settings singleton. Override in tests via dependency injection."""
    return Settings()
