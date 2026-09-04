"""
Pydantic request/response models for the SecureRegex API.

All models use ``model_config = ConfigDict(extra='forbid')`` so unexpected
fields are rejected at the boundary rather than silently ignored.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, ConfigDict


# ── Shared config ──────────────────────────────────────────────────────────────

_strict = ConfigDict(extra="forbid")


# ── Request models ─────────────────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    """POST /api/analyze request body."""
    model_config = _strict

    regex: str = Field(
        ...,
        description="Regular expression pattern to analyze.",
        min_length=1,
    )


class TestRequest(BaseModel):
    """POST /api/test request body."""
    model_config = _strict

    regex: str = Field(..., description="Regex pattern to compile.", min_length=1)
    input: str = Field(..., description="String to test against the compiled DFA.")


# ── Sub-shapes used in responses ───────────────────────────────────────────────

class PositionInfo(BaseModel):
    line:   int
    column: int


class ErrorDetail(BaseModel):
    """Structured error returned at any pipeline stage."""
    error:    str
    message:  str
    position: PositionInfo | None = None
    char:     str | None = None
    detail:   str | None = None


class PipelineStats(BaseModel):
    """Computed statistics about the compiled regex."""
    regex_length:         int
    token_count:          int
    ast_node_count:       int
    nfa_states:           int
    nfa_transitions:      int
    dfa_states:           int
    dfa_transitions:      int
    minimized_dfa_states: int
    dfa_reduction_pct:    float
    overall_security_risk: str


class DiagnosticItem(BaseModel):
    """A single semantic diagnostic (SEM001, etc.)."""
    severity: str
    code:     str
    message:  str
    location: dict[str, Any] | None = None


class SecurityFindingOut(BaseModel):
    rule_id:        str
    risk_level:     str
    title:          str
    reason:         str
    explanation:    str
    recommendation: str
    location:       dict[str, int] | None = None


class SecurityReportOut(BaseModel):
    overall_risk: str
    findings:     list[SecurityFindingOut]
    caveat:       str


# ── Success response models ────────────────────────────────────────────────────

class AnalyzeResponse(BaseModel):
    """Full pipeline result returned by POST /api/analyze."""

    success:        bool
    # Pipeline stages
    tokens:         list[dict[str, Any]]
    ast:            dict[str, Any]
    nfa:            dict[str, Any]
    dfa:            dict[str, Any]
    minimized_dfa:  dict[str, Any]
    # Analysis
    diagnostics:    list[DiagnosticItem]
    security:       SecurityReportOut
    stats:          PipelineStats


class TestResponse(BaseModel):
    """Result returned by POST /api/test."""

    matched: bool
    path:    list[int]   # DFA state IDs visited in order (including start)


# ── Error response model ───────────────────────────────────────────────────────

class ErrorResponse(BaseModel):
    """Returned on any pipeline failure (HTTP 4xx)."""

    success: bool = False
    stage:   str              # 'lexer' | 'parser' | 'semantic' | 'nfa' | 'dfa' | 'input'
    error:   ErrorDetail
    # Semantic failures may include a list of diagnostics as well
    diagnostics: list[DiagnosticItem] | None = None
