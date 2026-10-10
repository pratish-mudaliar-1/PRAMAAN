"""tests/unit/test_errors.py — RFC 9457 error model unit tests."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.errors import (
    AuthorizationError,
    NotFoundError,
    PramaanError,
    register_exception_handlers,
)


def make_test_app() -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/not-found")
    async def raise_not_found() -> None:
        raise NotFoundError("Resource XYZ not found")

    @app.get("/authz")
    async def raise_authz() -> None:
        raise AuthorizationError("Access denied to centre-1")

    @app.get("/validation-error")
    async def raise_pydantic() -> None:
        from pydantic import BaseModel, ValidationError as PydanticValError
        class M(BaseModel):
            x: int
        M(x="not-an-int")  # type: ignore[arg-type]

    @app.get("/ok")
    async def ok() -> dict[str, str]:
        return {"status": "ok"}

    return app


@pytest.fixture
def client() -> TestClient:
    return TestClient(make_test_app(), raise_server_exceptions=False)


def test_not_found_returns_problem_json(client: TestClient) -> None:
    resp = client.get("/not-found")
    assert resp.status_code == 404
    assert resp.headers["content-type"] == "application/problem+json"
    body = resp.json()
    assert body["status"] == 404
    assert "XYZ" in body["detail"]
    assert body["type"] != ""


def test_authz_error_returns_403(client: TestClient) -> None:
    resp = client.get("/authz")
    assert resp.status_code == 403
    assert resp.json()["type"] == "/problems/access-denied"


def test_ok_endpoint_not_affected(client: TestClient) -> None:
    resp = client.get("/ok")
    assert resp.status_code == 200


def test_problem_detail_no_stack_trace(client: TestClient) -> None:
    resp = client.get("/not-found")
    body = resp.json()
    assert "traceback" not in body
    assert "stack" not in body
