"""
Diagnostic dataclass and Severity enum for semantic analysis.

Each diagnostic carries:
  severity  – ERROR stops the pipeline; WARNING allows continuation
  code      – machine-readable identifier (e.g. "SEM001")
  message   – human-readable description
  position  – 1-indexed column in the original pattern, or None
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Severity(Enum):
    ERROR   = "ERROR"
    WARNING = "WARNING"


@dataclass(frozen=True)
class Diagnostic:
    """A single structured finding from semantic analysis.

    Attributes
    ----------
    severity : Severity
        ERROR-level diagnostics halt the pipeline; WARNING-level allow
        continuation with degraded accuracy.
    code     : str
        Short machine-readable code (SEM001 … SEMxxx).
    message  : str
        Human-readable description of the finding.
    position : int | None
        1-indexed column of the offending construct, or None when
        source-location information is unavailable.
    """

    severity: Severity
    code:     str
    message:  str
    position: int | None = None

    @property
    def is_error(self) -> bool:
        """True when this diagnostic will halt the pipeline."""
        return self.severity is Severity.ERROR

    def to_dict(self) -> dict:
        """Return a JSON-serialisable representation."""
        d: dict = {
            "severity": self.severity.value,
            "code":     self.code,
            "message":  self.message,
        }
        if self.position is not None:
            d["position"] = {"line": 1, "column": self.position}
        return d

    def __str__(self) -> str:  # pragma: no cover
        loc = f" (col {self.position})" if self.position is not None else ""
        return f"[{self.severity.value}] {self.code}{loc}: {self.message}"
