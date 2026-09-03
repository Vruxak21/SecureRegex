"""
Top-level API router — aggregates all versioned sub-routers.

During Phase 0 this only exposes a /info endpoint so the frontend can
verify end-to-end connectivity beyond the raw /health check.
Subsequent phases will add /analyze, /test, etc.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.config import settings

api_router = APIRouter()


@api_router.get("/info", tags=["API"])
async def info() -> dict:
    """Return API metadata — used by the frontend to display version info."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "limits": {
            "max_regex_length": settings.max_regex_length,
            "max_input_length": settings.max_input_length,
            "max_nfa_states": settings.max_nfa_states,
            "max_dfa_states": settings.max_dfa_states,
            "max_computation_steps": settings.max_computation_steps,
        },
    }
