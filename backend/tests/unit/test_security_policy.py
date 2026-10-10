"""tests/unit/test_security_policy.py — RBAC policy unit tests."""
import pytest

from app.core.security.policy import Policy, Principal
from app.core.errors import AuthorizationError


def make_principal(
    roles: list[str],
    subject: str = "u1",
    state_code: str | None = None,
    centre_ids: list[str] | None = None,
) -> Principal:
    claims = {
        "sub": subject,
        "roles": roles,
        "state_code": state_code,
        "centre_ids": centre_ids or [],
    }
    return Principal.from_claims(claims)


# ── require_read ───────────────────────────────────────────────────────────────

def test_all_roles_can_read() -> None:
    for role in ["national_admin", "state_officer", "inspector", "training_centre", "auditor"]:
        p = make_principal([role])
        Policy.require_read(p)  # should not raise


def test_empty_role_cannot_read() -> None:
    p = make_principal([])
    with pytest.raises(AuthorizationError):
        Policy.require_read(p)


# ── require_write ──────────────────────────────────────────────────────────────

def test_write_allowed_roles() -> None:
    for role in ["national_admin", "state_officer", "inspector"]:
        p = make_principal([role])
        Policy.require_write(p)


def test_write_denied_for_tc_and_auditor() -> None:
    for role in ["training_centre", "auditor"]:
        p = make_principal([role])
        with pytest.raises(AuthorizationError):
            Policy.require_write(p)


# ── require_admin ──────────────────────────────────────────────────────────────

def test_admin_only_national() -> None:
    p = make_principal(["national_admin"])
    Policy.require_admin(p)


def test_admin_denied_for_non_national() -> None:
    for role in ["state_officer", "inspector", "training_centre", "auditor"]:
        p = make_principal([role])
        with pytest.raises(AuthorizationError):
            Policy.require_admin(p)


# ── centre_filter ──────────────────────────────────────────────────────────────

def test_national_admin_has_no_filter() -> None:
    p = make_principal(["national_admin"])
    assert Policy.centre_filter(p) is None


def test_auditor_has_no_filter() -> None:
    p = make_principal(["auditor"])
    assert Policy.centre_filter(p) is None


def test_inspector_filter_is_their_centres() -> None:
    centres = ["c1", "c2"]
    p = make_principal(["inspector"], centre_ids=centres)
    assert set(Policy.centre_filter(p)) == set(centres)  # type: ignore[arg-type]


def test_training_centre_filter_is_single_centre() -> None:
    p = make_principal(["training_centre"], centre_ids=["c-abc"])
    assert Policy.centre_filter(p) == ["c-abc"]


def test_empty_role_gets_empty_filter() -> None:
    p = make_principal([])
    assert Policy.centre_filter(p) == []


# ── require_centre_access ──────────────────────────────────────────────────────

def test_national_admin_can_access_any_centre() -> None:
    p = make_principal(["national_admin"])
    Policy.require_centre_access(p, "any-centre-id")


def test_inspector_can_access_assigned_centre() -> None:
    p = make_principal(["inspector"], centre_ids=["c1", "c2"])
    Policy.require_centre_access(p, "c1")


def test_inspector_cannot_access_unassigned_centre() -> None:
    p = make_principal(["inspector"], centre_ids=["c1"])
    with pytest.raises(AuthorizationError):
        Policy.require_centre_access(p, "c2")


def test_tc_cannot_access_other_centre() -> None:
    p = make_principal(["training_centre"], centre_ids=["mine"])
    with pytest.raises(AuthorizationError):
        Policy.require_centre_access(p, "not-mine")
