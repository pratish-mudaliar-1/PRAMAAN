"""app/core/security/jwt.py — JWT verification supporting local dev issuer and real JWKS."""
from __future__ import annotations

import json
import time
from functools import lru_cache
from typing import Any

import httpx
from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError

from app.core.errors import AuthenticationError
from app.core.logging import get_logger

logger = get_logger(__name__)

# ── Dev issuer (used when AUTH_JWKS_URL is empty / dev environment) ───────────

def create_dev_token(
    subject: str,
    roles: list[str],
    centre_ids: list[str] | None = None,
    state_code: str | None = None,
    *,
    secret: str,
    algorithm: str = "HS256",
    audience: str = "pramaan-api",
    issuer: str = "http://localhost:8000/dev-oidc",
    ttl_seconds: int = 3600,
) -> str:
    """Create a signed JWT for dev/testing. NEVER use in production."""
    now = int(time.time())
    claims: dict[str, Any] = {
        "sub": subject,
        "iss": issuer,
        "aud": audience,
        "iat": now,
        "exp": now + ttl_seconds,
        "roles": roles,
    }
    if centre_ids:
        claims["centre_ids"] = centre_ids
    if state_code:
        claims["state_code"] = state_code
    return jwt.encode(claims, secret, algorithm=algorithm)


# ── JWKS cache ─────────────────────────────────────────────────────────────────

class JWKSCache:
    """Fetches and caches JWKS keys with a TTL."""

    _TTL = 3600  # seconds

    def __init__(self, jwks_url: str) -> None:
        self._url = jwks_url
        self._keys: list[dict[str, Any]] = []
        self._fetched_at: float = 0.0

    def _is_stale(self) -> bool:
        return time.time() - self._fetched_at > self._TTL

    def get_keys(self) -> list[dict[str, Any]]:
        if self._is_stale():
            try:
                resp = httpx.get(self._url, timeout=5.0)
                resp.raise_for_status()
                self._keys = resp.json().get("keys", [])
                self._fetched_at = time.time()
            except Exception as exc:  # noqa: BLE001
                logger.error("jwks_fetch_failed", url=self._url, error=str(exc))
                if not self._keys:
                    raise AuthenticationError("JWKS fetch failed; cannot verify token") from exc
        return self._keys


# ── Verifier ───────────────────────────────────────────────────────────────────

class TokenVerifier:
    """Verify a JWT using either the configured JWKS endpoint or local dev secret."""

    def __init__(
        self,
        *,
        jwks_url: str = "",
        dev_secret: str = "",
        algorithm: str = "RS256",
        audience: str = "pramaan-api",
        issuer: str = "",
        clock_skew_seconds: int = 30,
    ) -> None:
        self._dev_secret = dev_secret
        self._algorithm = algorithm if not dev_secret else "HS256"
        self._audience = audience
        self._issuer = issuer
        self._clock_skew = clock_skew_seconds
        self._jwks_cache = JWKSCache(jwks_url) if jwks_url and not dev_secret else None

    def verify(self, token: str) -> dict[str, Any]:
        """Verify token and return claims dict. Raises AuthenticationError on failure."""
        options = {
            "verify_exp": True,
            "leeway": self._clock_skew,
        }
        try:
            if self._dev_secret:
                claims = jwt.decode(
                    token,
                    self._dev_secret,
                    algorithms=["HS256"],
                    audience=self._audience,
                    options=options,
                )
            else:
                assert self._jwks_cache is not None
                keys = self._jwks_cache.get_keys()
                claims = jwt.decode(
                    token,
                    {"keys": keys},
                    algorithms=[self._algorithm],
                    audience=self._audience,
                    options=options,
                )
        except ExpiredSignatureError as exc:
            raise AuthenticationError("Token has expired") from exc
        except JWTError as exc:
            raise AuthenticationError(f"Invalid token: {exc}") from exc

        if self._issuer and claims.get("iss") != self._issuer:
            raise AuthenticationError(f"Invalid issuer: {claims.get('iss')}")

        return claims


@lru_cache(maxsize=1)
def get_token_verifier() -> TokenVerifier:
    """Return cached verifier built from settings. Swap in tests via DI."""
    from app.core.config import get_settings
    s = get_settings()
    dev_secret = ""
    if not s.is_production:
        dev_secret = s.auth.dev_jwt_secret.get_secret_value()
    return TokenVerifier(
        jwks_url=s.auth.jwks_url if not dev_secret else "",
        dev_secret=dev_secret,
        algorithm=s.auth.jwt_algorithm,
        audience=s.auth.jwt_audience,
        issuer=s.auth.oidc_issuer,
        clock_skew_seconds=s.auth.jwt_clock_skew_seconds,
    )
