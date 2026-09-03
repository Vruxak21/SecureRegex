"""
Phase 0 — smoke tests.

These tests verify that:
  1. The FastAPI app can be instantiated.
  2. /health returns {"status": "ok"} with HTTP 200.
  3. /api/v1/info returns expected keys and respects configured limits.
  4. The Settings object loads with correct defaults.
  5. The SecureRegexError hierarchy produces well-formed dicts.

No regex engine code is exercised here — that starts in Phase 1.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.config import Settings
from app.exceptions import (
    SecureRegexError,
    RegexTooLongError,
    ParseError,
    SimulationTimeoutError,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
async def client():
    """Async test client wired directly to the ASGI app (no real socket)."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


# ── /health ──────────────────────────────────────────────────────────────────

class TestHealthEndpoint:
    async def test_health_returns_200(self, client: AsyncClient):
        response = await client.get("/health")
        assert response.status_code == 200

    async def test_health_body_has_status_ok(self, client: AsyncClient):
        data = (await client.get("/health")).json()
        assert data["status"] == "ok"

    async def test_health_body_has_version(self, client: AsyncClient):
        data = (await client.get("/health")).json()
        assert "version" in data

    async def test_health_body_has_app_name(self, client: AsyncClient):
        data = (await client.get("/health")).json()
        assert data["app"] == "SecureRegex"


# ── /api/v1/info ─────────────────────────────────────────────────────────────

class TestInfoEndpoint:
    async def test_info_returns_200(self, client: AsyncClient):
        response = await client.get("/api/v1/info")
        assert response.status_code == 200

    async def test_info_has_limits_block(self, client: AsyncClient):
        data = (await client.get("/api/v1/info")).json()
        assert "limits" in data

    async def test_info_limits_have_expected_keys(self, client: AsyncClient):
        limits = (await client.get("/api/v1/info")).json()["limits"]
        expected_keys = {
            "max_regex_length",
            "max_input_length",
            "max_nfa_states",
            "max_dfa_states",
            "max_computation_steps",
        }
        assert expected_keys.issubset(limits.keys())

    async def test_info_limits_are_positive_ints(self, client: AsyncClient):
        limits = (await client.get("/api/v1/info")).json()["limits"]
        for key, value in limits.items():
            assert isinstance(value, int) and value > 0, (
                f"Limit {key!r} must be a positive integer, got {value!r}"
            )


# ── Settings ──────────────────────────────────────────────────────────────────

class TestSettings:
    def test_default_max_regex_length(self):
        s = Settings()
        assert s.max_regex_length == 1_000

    def test_default_max_computation_steps(self):
        s = Settings()
        assert s.max_computation_steps == 1_000_000

    def test_default_cors_origins_include_vite(self):
        s = Settings()
        assert any("5173" in origin for origin in s.cors_origins)

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("SECUREREGEX_MAX_REGEX_LENGTH", "42")
        s = Settings()
        assert s.max_regex_length == 42


# ── Exceptions ────────────────────────────────────────────────────────────────

class TestExceptions:
    def test_base_error_to_dict(self):
        err = SecureRegexError("something went wrong")
        d = err.to_dict()
        assert d["error"] == "SECUREREGEX_ERROR"
        assert d["message"] == "something went wrong"

    def test_base_error_detail(self):
        err = SecureRegexError("msg", detail="extra info")
        assert err.to_dict()["detail"] == "extra info"

    def test_regex_too_long_is_subclass(self):
        err = RegexTooLongError("too long")
        assert isinstance(err, SecureRegexError)
        assert err.status_code == 422
        assert err.error_code == "REGEX_TOO_LONG"

    def test_parse_error_status(self):
        err = ParseError("unexpected token")
        assert err.status_code == 400
        assert err.error_code == "PARSE_ERROR"

    def test_simulation_timeout_status(self):
        err = SimulationTimeoutError("timed out")
        assert err.status_code == 408

    async def test_unhandled_domain_error_returns_structured_json(
        self, client: AsyncClient
    ):
        """
        Inject a route that raises a SecureRegexError and verify the handler
        returns a structured JSON body (not a raw 500 traceback).
        """
        from fastapi import APIRouter
        from app.exceptions import ParseError as PE

        router = APIRouter()

        @router.get("/_test_error")
        async def _raise():
            raise PE("intentional parse error for testing")

        app.include_router(router)

        response = await client.get("/_test_error")
        assert response.status_code == 400
        body = response.json()
        assert body["error"] == "PARSE_ERROR"
        assert "message" in body
