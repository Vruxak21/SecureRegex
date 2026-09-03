"""
Structured exception hierarchy for SecureRegex.

All domain errors are subclasses of SecureRegexError so that a single
FastAPI exception handler can catch them and return a consistent JSON body
instead of raw stack traces.
"""

from __future__ import annotations


class SecureRegexError(Exception):
    """Base class for all SecureRegex domain errors."""

    # HTTP status code to use when this error is converted to a response.
    status_code: int = 400
    error_code: str = "SECUREREGEX_ERROR"

    def __init__(self, message: str, *, detail: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail

    def to_dict(self) -> dict:
        payload: dict = {
            "error": self.error_code,
            "message": self.message,
        }
        if self.detail:
            payload["detail"] = self.detail
        return payload


# ── Input validation ─────────────────────────────────────────────────────────

class ValidationError(SecureRegexError):
    """Raised when user-supplied input fails basic validation."""
    status_code = 422
    error_code = "VALIDATION_ERROR"


class RegexTooLongError(ValidationError):
    """Regex pattern exceeds the configured maximum length."""
    error_code = "REGEX_TOO_LONG"


class InputTooLongError(ValidationError):
    """Test input string exceeds the configured maximum length."""
    error_code = "INPUT_TOO_LONG"


# ── Lexer / Parser ───────────────────────────────────────────────────────────

class LexerError(SecureRegexError):
    """Raised when the lexer encounters an unrecognised or invalid token.

    Extra attributes
    ----------------
    position : int | None
        1-indexed column number where the error occurred.
    char : str | None
        The offending character (single char or escape sequence).
    """

    error_code = "LEXER_ERROR"

    def __init__(
        self,
        message: str,
        *,
        position: int | None = None,
        char: str | None = None,
        detail: str | None = None,
    ) -> None:
        super().__init__(message, detail=detail)
        self.position = position
        self.char = char

    def to_dict(self) -> dict:
        d = super().to_dict()
        if self.position is not None:
            d["position"] = {"line": 1, "column": self.position}
        if self.char is not None:
            d["char"] = self.char
        return d


class ParseError(SecureRegexError):
    """Raised when the parser detects a syntax error.

    Extra attributes
    ----------------
    position : int | None
        1-indexed column number where the error was detected.
    """

    error_code = "PARSE_ERROR"

    def __init__(
        self,
        message: str,
        *,
        position: int | None = None,
        detail: str | None = None,
    ) -> None:
        super().__init__(message, detail=detail)
        self.position = position

    def to_dict(self) -> dict:
        d = super().to_dict()
        if self.position is not None:
            d["position"] = {"line": 1, "column": self.position}
        return d


# ── Semantic analysis ────────────────────────────────────────────────────────

class SemanticError(SecureRegexError):
    """Raised when semantic analysis finds an invalid construct."""
    error_code = "SEMANTIC_ERROR"


# ── Automata construction ────────────────────────────────────────────────────

class NFAConstructionError(SecureRegexError):
    """Raised when NFA construction fails (e.g. state limit exceeded)."""
    error_code = "NFA_CONSTRUCTION_ERROR"


class DFAConstructionError(SecureRegexError):
    """Raised when DFA construction fails (e.g. state limit exceeded)."""
    error_code = "DFA_CONSTRUCTION_ERROR"


# ── Simulation ───────────────────────────────────────────────────────────────

class SimulationTimeoutError(SecureRegexError):
    """Raised when DFA simulation exceeds the configured step limit."""
    status_code = 408
    error_code = "SIMULATION_TIMEOUT"
