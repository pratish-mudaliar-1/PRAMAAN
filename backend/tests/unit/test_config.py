"""tests/unit/test_config.py — Settings configuration unit tests."""
import os
import pytest
from pydantic import ValidationError


def test_default_settings_load() -> None:
    from app.core.config import Settings
    s = Settings()
    assert s.environment == "development"
    assert 0.0 <= s.default_t_green <= 1.0
    assert 0.0 <= s.default_t_amber <= 1.0
    assert s.default_t_green > s.default_t_amber


def test_threshold_validation_rejects_out_of_range(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRAMAAN_DEFAULT_T_GREEN", "1.5")
    from app.core.config import Settings
    with pytest.raises((ValidationError, ValueError)):
        Settings()


def test_db_async_url_format(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DB_ASYNC_URL_OVERRIDE", raising=False)
    from app.core.config import DatabaseSettings
    db = DatabaseSettings(async_url_override="")
    url = db.async_url
    assert url.startswith("postgresql+asyncpg://")
    assert db.name in url


def test_redis_url_format() -> None:
    from app.core.config import RedisSettings
    r = RedisSettings()
    assert r.url.startswith("redis://")


def test_auth_jwks_default_set_from_issuer() -> None:
    from app.core.config import AuthSettings
    a = AuthSettings()
    assert "/.well-known/jwks.json" in a.jwks_url


def test_is_production_flag() -> None:
    from app.core.config import Settings
    s = Settings(environment="production")
    assert s.is_production is True
    s2 = Settings(environment="development")
    assert s2.is_production is False
