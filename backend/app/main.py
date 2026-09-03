"""
SecureRegex — FastAPI application entry-point.

Responsibilities:
  - Create the FastAPI app instance with metadata.
  - Register CORS middleware (so the Vite dev server can reach it).
  - Register a global exception handler that converts all SecureRegexError
    subclasses into structured JSON — raw stack traces are never surfaced.
  - Mount the API router (v1).
  - Expose /health for infrastructure health-checks.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.exceptions import SecureRegexError
from app.api.router import api_router

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

# ── App factory ──────────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "Compiler-based Regular Expression Security Analyzer and Automata Optimizer. "
            "Implements a hand-written Lexer → Parser → NFA → DFA pipeline."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # ── CORS ─────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Global structured error handler ──────────────────────────────────────
    @app.exception_handler(SecureRegexError)
    async def secureregex_error_handler(
        request: Request, exc: SecureRegexError
    ) -> JSONResponse:
        logger.warning(
            "SecureRegexError [%s]: %s", exc.error_code, exc.message
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.to_dict(),
        )

    # Catch-all for unexpected exceptions — log the full traceback server-side,
    # but only return a generic message to the client.
    @app.exception_handler(Exception)
    async def unhandled_error_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        logger.exception("Unhandled exception: %s", exc)
        return JSONResponse(
            status_code=500,
            content={
                "error": "INTERNAL_ERROR",
                "message": "An unexpected error occurred. Please try again.",
            },
        )

    # ── Routes ───────────────────────────────────────────────────────────────
    @app.get("/health", tags=["Infrastructure"])
    async def health() -> dict:
        """Lightweight health-check used by Docker, load-balancers, and the UI."""
        return {
            "status": "ok",
            "version": settings.app_version,
            "app": settings.app_name,
        }

    app.include_router(api_router, prefix="/api/v1")

    logger.info("%s v%s started (debug=%s)", settings.app_name, settings.app_version, settings.debug)
    return app


app = create_app()
