"""
Top-level API router — aggregates all versioned sub-routers.

Endpoints
---------
GET  /api/v1/info          — API metadata + configured limits
POST /api/v1/analyze       — Full pipeline analysis
POST /api/v1/test          — DFA match test with state path
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.config     import settings
from app.exceptions import SecureRegexError

from app.api.models   import AnalyzeRequest, TestRequest
from app.api.pipeline import run_analyze, run_test

logger = logging.getLogger(__name__)

api_router = APIRouter()


# ── GET /info ─────────────────────────────────────────────────────────────────

@api_router.get("/info", tags=["API"])
async def info() -> dict:
    """Return API metadata — used by the frontend to display version info."""
    return {
        "name":    settings.app_name,
        "version": settings.app_version,
        "limits": {
            "max_regex_length":      settings.max_regex_length,
            "max_input_length":      settings.max_input_length,
            "max_nfa_states":        settings.max_nfa_states,
            "max_dfa_states":        settings.max_dfa_states,
            "max_computation_steps": settings.max_computation_steps,
        },
    }


# ── POST /analyze ─────────────────────────────────────────────────────────────

@api_router.post(
    "/analyze",
    tags=["Analysis"],
    status_code=status.HTTP_200_OK,
    summary="Run the full regex compiler pipeline",
    response_description=(
        "On success: all pipeline stage outputs + security report + stats. "
        "On failure: structured error with the stage name and message."
    ),
)
async def analyze(body: AnalyzeRequest):
    """
    **Full pipeline**: regex → Lexer → Parser → Semantic → NFA → DFA →
    Minimization → Security Analysis.

    Stops at the first failing stage and returns a structured error body
    (HTTP 4xx).  Raw tracebacks are never surfaced.
    """
    # All SecureRegexError subclasses are caught by the global handler in main.py
    # and converted to structured JSON responses — we just let them propagate.
    result = run_analyze(body.regex)
    return result


# ── POST /test ────────────────────────────────────────────────────────────────

@api_router.post(
    "/test",
    tags=["Analysis"],
    status_code=status.HTTP_200_OK,
    summary="Test a string against a compiled DFA and return the state path",
    response_description=(
        "matched: bool — whether the DFA accepted the input. "
        "path: list[int] — DFA state IDs visited (for visualisation)."
    ),
)
async def test(body: TestRequest):
    """
    Compile *regex* to a minimized DFA, then simulate *input* against it.

    Returns the accept/reject result plus the sequence of DFA states visited
    (start state through final state), suitable for animated graph traversal
    in the frontend visualiser.
    """
    result = run_test(body.regex, body.input)
    return result
