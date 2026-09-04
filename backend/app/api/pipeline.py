"""
Pipeline orchestrator — runs the full compiler chain and assembles responses.

Stage order:
    1. Input validation    (length guard from settings)
    2. Lexer               → list[Token]
    3. Parser              → ASTNode
    4. Semantic analysis   → list[Diagnostic]  (ERROR stops pipeline)
    5. NFA construction    → NFA
    6. DFA construction    → DFA
    7. DFA minimization    → (DFA, MinimizationStats)
    8. Security analysis   → SecurityReport
    9. Statistics          → PipelineStats

Any domain exception at stages 2–7 raises the appropriate SecureRegexError
subclass; the FastAPI exception handler in main.py catches those and returns
structured JSON.  Raw Python exceptions are never allowed to propagate.

This module also provides the DFA test function (state-path simulation).
"""

from __future__ import annotations

from app.config     import settings
from app.exceptions import (
    DFAConstructionError, InputTooLongError, RegexTooLongError, SemanticError,
    SimulationTimeoutError,
)

from app.lexer      import tokenize
from app.lexer.token import TokenType
from app.parser     import parse_pattern
from app.semantic   import analyze as semantic_analyze
from app.nfa        import build_nfa
from app.dfa        import build_dfa, build_trans_map
from app.optimizer  import minimize_dfa
from app.security   import analyze_security

from app.api.models import (
    AnalyzeResponse, TestResponse, ErrorResponse,
    PipelineStats, SecurityReportOut, SecurityFindingOut,
    DiagnosticItem, ErrorDetail, PositionInfo,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _count_ast_nodes(node_dict: dict) -> int:
    """Recursively count nodes in a serialised AST dict."""
    count = 1
    for v in node_dict.values():
        if isinstance(v, dict):
            count += _count_ast_nodes(v)
        elif isinstance(v, list):
            for item in v:
                if isinstance(item, dict):
                    count += _count_ast_nodes(item)
    return count


def _token_to_dict(tok) -> dict:
    return {
        "type":   tok.type.name,
        "value":  tok.value,
        "column": tok.column,
    }


def _diag_to_model(d) -> DiagnosticItem:
    loc = None
    if hasattr(d, "location") and d.location:
        loc = d.location
    elif hasattr(d, "position") and d.position:
        loc = {"line": 1, "column": d.position}
    return DiagnosticItem(
        severity=d.severity,
        code=d.code,
        message=d.message,
        location=loc,
    )


def _security_report_to_model(report) -> SecurityReportOut:
    findings = [
        SecurityFindingOut(
            rule_id        = f.rule_id,
            risk_level     = f.risk_level,
            title          = f.title,
            reason         = f.reason,
            explanation    = f.explanation,
            recommendation = f.recommendation,
            location       = (
                {"start": f.location[0], "end": f.location[1]}
                if f.location else None
            ),
        )
        for f in report.findings
    ]
    return SecurityReportOut(
        overall_risk = report.overall_risk,
        findings     = findings,
        caveat       = report.caveat,
    )


def _exc_to_error_detail(exc) -> ErrorDetail:
    pos = None
    if hasattr(exc, "position") and exc.position is not None:
        pos = PositionInfo(line=1, column=exc.position)
    char = getattr(exc, "char", None)
    detail = getattr(exc, "detail", None)
    return ErrorDetail(
        error   = exc.error_code,
        message = exc.message,
        position= pos,
        char    = char,
        detail  = detail,
    )


# ── Stat simulation for /api/test (with path tracking) ────────────────────────

def _dfa_run_with_path(dfa, string: str, max_steps: int) -> tuple[bool, list[int]]:
    """Simulate the minimized DFA on *string*, recording the state path.

    Returns (accepted, path) where path includes the start state and every
    state reached after consuming each character.

    Raises SimulationTimeoutError if len(string) > max_steps.
    """
    if len(string) > max_steps:
        raise SimulationTimeoutError(
            f"Input length {len(string)} exceeds the simulation step limit "
            f"({max_steps}). Reduce the input or raise SECUREREGEX_MAX_COMPUTATION_STEPS.",
        )
    tm = build_trans_map(dfa)
    current = dfa.start
    path = [current]
    for char in string:
        row = tm.get(current)
        if row is None or char not in row:
            return False, path   # dead transition — reject, path up to this point
        current = row[char]
        path.append(current)
    return current in dfa.accepting, path


# ── Main pipeline ──────────────────────────────────────────────────────────────

def run_analyze(regex: str) -> AnalyzeResponse:
    """Execute the full pipeline on *regex* and return an AnalyzeResponse.

    Raises subclasses of SecureRegexError on any stage failure so that the
    FastAPI handler converts them to structured JSON.
    """
    # Stage 0 — input validation
    if len(regex) > settings.max_regex_length:
        raise RegexTooLongError(
            f"Regex length {len(regex)} exceeds the maximum of "
            f"{settings.max_regex_length} characters.",
            detail=f"Set SECUREREGEX_MAX_REGEX_LENGTH to allow longer patterns.",
        )

    # Stage 1 — Lexer
    tokens = tokenize(regex)   # raises LexerError on bad input

    # Stage 2 — Parser
    ast = parse_pattern(regex)   # raises ParseError

    # Stage 3 — Semantic analysis
    diagnostics = semantic_analyze(ast)
    error_diags = [d for d in diagnostics if d.severity == "ERROR"]
    if error_diags:
        raise SemanticError(
            f"Semantic analysis found {len(error_diags)} error(s): "
            + "; ".join(d.message for d in error_diags),
        )

    # Stage 4 — NFA
    nfa = build_nfa(ast)   # raises NFAConstructionError if state limit hit

    # Stage 5 — DFA (subset construction)
    dfa = build_dfa(nfa, max_states=settings.max_dfa_states)  # raises DFAConstructionError

    # Stage 6 — Minimization
    min_dfa, min_stats = minimize_dfa(dfa)

    # Stage 7 — Security analysis (never raises; returns findings)
    sec_report = analyze_security(ast)

    # Stage 8 — Assemble stats
    ast_dict   = ast.to_dict()
    token_dicts = [_token_to_dict(t) for t in tokens if t.type != TokenType.EOF]

    stats = PipelineStats(
        regex_length          = len(regex),
        token_count           = len(token_dicts),
        ast_node_count        = _count_ast_nodes(ast_dict),
        nfa_states            = len(nfa.states),
        nfa_transitions       = len(nfa.transitions),
        dfa_states            = len(dfa.states),
        dfa_transitions       = len(dfa.transitions),
        minimized_dfa_states  = min_stats.minimized_states,
        dfa_reduction_pct     = min_stats.reduction_pct,
        overall_security_risk = sec_report.overall_risk,
    )

    return AnalyzeResponse(
        success       = True,
        tokens        = token_dicts,
        ast           = ast_dict,
        nfa           = nfa.to_dict(),
        dfa           = dfa.to_dict(),
        minimized_dfa = min_dfa.to_dict(),
        diagnostics   = [_diag_to_model(d) for d in diagnostics],
        security      = _security_report_to_model(sec_report),
        stats         = stats,
    )


def run_test(regex: str, input_str: str) -> TestResponse:
    """Compile *regex* to a minimized DFA, then test *input_str* against it.

    Returns the match result and the sequence of DFA states visited.
    Raises SecureRegexError subclasses on any pipeline failure.
    """
    # Input validation
    if len(regex) > settings.max_regex_length:
        raise RegexTooLongError(
            f"Regex length {len(regex)} exceeds the maximum "
            f"of {settings.max_regex_length}.",
        )
    if len(input_str) > settings.max_input_length:
        raise InputTooLongError(
            f"Input length {len(input_str)} exceeds the maximum "
            f"of {settings.max_input_length}.",
        )

    # Run pipeline stages (reuse same logic; could be cached in production)
    ast     = parse_pattern(regex)
    diags   = semantic_analyze(ast)
    if any(d.severity == "ERROR" for d in diags):
        raise SemanticError("Semantic errors prevent compilation.")
    nfa     = build_nfa(ast)
    dfa     = build_dfa(nfa, max_states=settings.max_dfa_states)
    min_dfa, _ = minimize_dfa(dfa)

    matched, path = _dfa_run_with_path(
        min_dfa, input_str, settings.max_computation_steps
    )
    return TestResponse(matched=matched, path=path)
