"""app/api/v1/deps.py — FastAPI dependency injectors for v1 routes."""
from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AuthenticationError, AuthorizationError
from app.core.security.jwt import get_token_verifier
from app.core.security.policy import Policy, Principal
from app.db.base import AsyncSession as _AS

_bearer = HTTPBearer(auto_error=False)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an AsyncSession; session factory is set up in app lifespan."""
    from app.main import get_session_factory
    factory = get_session_factory()
    async with factory() as session:
        yield session


DbSession = Annotated[AsyncSession, Depends(get_db_session)]


def _extract_principal(credentials: HTTPAuthorizationCredentials | None) -> Principal:
    if credentials is None:
        raise AuthenticationError("Missing Authorization header")
    verifier = get_token_verifier()
    try:
        claims = verifier.verify(credentials.credentials)
    except AuthenticationError:
        raise
    return Principal.from_claims(claims)


async def get_current_principal(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> Principal:
    return _extract_principal(credentials)


CurrentPrincipal = Annotated[Principal, Depends(get_current_principal)]
