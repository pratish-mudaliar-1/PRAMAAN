"""app/core/security/policy.py — Single RBAC policy enforcement layer.

ALL access decisions happen here. Routers call `Policy.require_*` methods;
they never do auth checks themselves.

Role taxonomy:
  national_admin  — full read/write, all centres, all states
  state_officer   — read/write within their state_code; cannot modify thresholds globally
  inspector       — read/write on assigned centre_ids
  training_centre — read-only own centre (centre_id matches sub claim)
  auditor         — read-only on everything, all centres

Row-level scoping rules per role:
  national_admin  → no filter
  state_officer   → WHERE centre.state_code = token.state_code
  inspector       → WHERE centre.id IN token.centre_ids
  training_centre → WHERE centre.id = token.centre_id (single)
  auditor         → no filter (read-only)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from app.core.errors import AuthorizationError

Role = Literal["national_admin", "state_officer", "inspector", "training_centre", "auditor"]

_READ_ROLES: frozenset[Role] = frozenset(
    {"national_admin", "state_officer", "inspector", "training_centre", "auditor"}
)
_WRITE_ROLES: frozenset[Role] = frozenset(
    {"national_admin", "state_officer", "inspector"}
)
_ADMIN_ROLES: frozenset[Role] = frozenset({"national_admin"})
_THRESHOLD_ROLES: frozenset[Role] = frozenset({"national_admin", "state_officer"})


@dataclass(frozen=True)
class Principal:
    """Parsed, validated identity extracted from a verified JWT."""

    subject: str                          # "sub" claim — opaque user ID
    roles: tuple[Role, ...]
    state_code: str | None = None         # set for state_officer
    centre_ids: tuple[str, ...] = field(default_factory=tuple)   # set for inspector / training_centre

    @classmethod
    def from_claims(cls, claims: dict) -> "Principal":  # type: ignore[type-arg]
        raw_roles = claims.get("roles", [])
        roles: list[Role] = []
        for r in raw_roles:
            if r in _READ_ROLES:
                roles.append(r)  # type: ignore[arg-type]
        centre_ids_raw: list[str] = claims.get("centre_ids", []) or []
        return cls(
            subject=str(claims["sub"]),
            roles=tuple(roles),
            state_code=claims.get("state_code"),
            centre_ids=tuple(centre_ids_raw),
        )

    @property
    def sub(self) -> str:
        return self.subject

    def has_role(self, *roles: Role) -> bool:
        return bool(set(self.roles) & set(roles))



class Policy:
    """Stateless policy engine. All methods raise AuthorizationError on deny."""

    @staticmethod
    def require_read(principal: Principal) -> None:
        if not principal.has_role(*_READ_ROLES):
            raise AuthorizationError("Insufficient permissions for read access")

    @staticmethod
    def require_write(principal: Principal) -> None:
        if not principal.has_role(*_WRITE_ROLES):
            raise AuthorizationError("Insufficient permissions for write access")

    @staticmethod
    def require_admin(principal: Principal) -> None:
        if not principal.has_role(*_ADMIN_ROLES):
            raise AuthorizationError("This operation requires national_admin role")

    @staticmethod
    def require_threshold_management(principal: Principal) -> None:
        if not principal.has_role(*_THRESHOLD_ROLES):
            raise AuthorizationError("Threshold management requires national_admin or state_officer role")

    @staticmethod
    def centre_filter(principal: Principal) -> list[str] | None:
        """Return list of allowed centre IDs, or None if unrestricted (national_admin / auditor).

        Callers must apply WHERE centre_id IN (...) when the list is not None.
        """
        if principal.has_role("national_admin", "auditor"):
            return None
        if principal.has_role("state_officer"):
            # Caller must also filter by state_code — returned separately
            return None
        if principal.has_role("inspector"):
            return list(principal.centre_ids)
        if principal.has_role("training_centre"):
            return list(principal.centre_ids)
        return []  # no access

    @staticmethod
    def state_filter(principal: Principal) -> str | None:
        """Return state_code to filter by, or None if unrestricted."""
        if principal.has_role("state_officer"):
            return principal.state_code
        return None

    @staticmethod
    def require_centre_access(principal: Principal, centre_id: str) -> None:
        """Raise AuthorizationError if principal cannot access this specific centre."""
        if principal.has_role("national_admin", "auditor"):
            return
        if principal.has_role("state_officer"):
            # state_code checked at query level; assume centre is in their state
            return
        if principal.has_role("inspector", "training_centre"):
            if centre_id not in principal.centre_ids:
                raise AuthorizationError(f"Access to centre {centre_id} is not permitted")
            return
        raise AuthorizationError("No centre access")
