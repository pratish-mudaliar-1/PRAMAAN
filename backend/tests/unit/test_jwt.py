"""tests/unit/test_jwt.py — JWT issuance and verification unit tests."""
import time
from typing import cast

import pytest

from app.core.security.jwt import TokenVerifier, create_dev_token
from app.core.errors import AuthenticationError

SECRET = "unit-test-secret"
AUDIENCE = "pramaan-api"
ISSUER = "http://test-issuer"


def _verifier() -> TokenVerifier:
    return TokenVerifier(
        dev_secret=SECRET,
        audience=AUDIENCE,
        issuer=ISSUER,
        clock_skew_seconds=5,
    )


def test_create_and_verify_dev_token() -> None:
    token = create_dev_token(
        subject="user-123",
        roles=["inspector"],
        secret=SECRET,
        audience=AUDIENCE,
        issuer=ISSUER,
    )
    claims = _verifier().verify(token)
    assert claims["sub"] == "user-123"
    assert "inspector" in claims["roles"]


def test_token_with_centre_ids() -> None:
    token = create_dev_token(
        subject="insp-1",
        roles=["inspector"],
        centre_ids=["c-1", "c-2"],
        secret=SECRET,
        audience=AUDIENCE,
        issuer=ISSUER,
    )
    claims = _verifier().verify(token)
    assert set(claims["centre_ids"]) == {"c-1", "c-2"}


def test_expired_token_raises() -> None:
    token = create_dev_token(
        subject="u",
        roles=["auditor"],
        secret=SECRET,
        audience=AUDIENCE,
        issuer=ISSUER,
        ttl_seconds=-3600,    # expired one hour ago — well outside the 5s leeway
    )
    with pytest.raises(AuthenticationError, match="expired"):
        _verifier().verify(token)


def test_wrong_secret_raises() -> None:
    token = create_dev_token(
        subject="u",
        roles=["auditor"],
        secret="different-secret",
        audience=AUDIENCE,
        issuer=ISSUER,
    )
    with pytest.raises(AuthenticationError):
        _verifier().verify(token)


def test_wrong_audience_raises() -> None:
    token = create_dev_token(
        subject="u",
        roles=["auditor"],
        secret=SECRET,
        audience="wrong-audience",
        issuer=ISSUER,
    )
    with pytest.raises(AuthenticationError):
        _verifier().verify(token)


def test_wrong_issuer_raises() -> None:
    token = create_dev_token(
        subject="u",
        roles=["auditor"],
        secret=SECRET,
        audience=AUDIENCE,
        issuer="http://evil-issuer",
    )
    # Our verifier expects ISSUER, token has evil-issuer
    with pytest.raises(AuthenticationError, match="issuer"):
        _verifier().verify(token)


def test_principal_from_claims_filters_unknown_roles() -> None:
    from app.core.security.policy import Principal
    claims = {
        "sub": "u",
        "roles": ["national_admin", "UNKNOWN_ROLE", "hacker"],
        "centre_ids": cast(list[str], []),
    }
    p = Principal.from_claims(claims)
    assert p.roles == ("national_admin",)
