"""
Security report data types.

SecurityFinding    — a single heuristic finding with rule ID, risk level, and location.
SecurityReport     — aggregate result with all findings, overall risk, and the
                     mandatory DFA-vs-backtracking caveat.

Risk levels (ordered LOW < MEDIUM < HIGH)
-----------------------------------------
HIGH   — Strong structural indicator; known to cause catastrophic backtracking
         in most backtracking regex engines.
MEDIUM — Ambiguous pattern that *may* cause super-linear backtracking; depends
         on the engine and the specific input.
LOW    — No elevated risk detected by the heuristic rules.
NONE   — No findings produced (alias for LOW in user-facing output).
"""

from __future__ import annotations

from dataclasses import dataclass


# ── Risk-level constants ──────────────────────────────────────────────────────

HIGH   = "HIGH"
MEDIUM = "MEDIUM"
LOW    = "LOW"
NONE   = "NONE"

# Ordered list used for comparisons (ascending severity)
RISK_ORDER: list[str] = [NONE, LOW, MEDIUM, HIGH]


# ── Standard disclaimer ───────────────────────────────────────────────────────

CAVEAT: str = (
    "Findings are heuristic risk indicators only. "
    "SecureRegex's own DFA-based engine does not backtrack and is therefore "
    "immune to ReDoS. However, the same pattern used in backtracking engines "
    "(Python re, JavaScript, Java, .NET, PCRE, etc.) may exhibit catastrophic "
    "backtracking on adversarial inputs. "
    "Treat each finding as a potential risk in those environments, "
    "not a confirmed vulnerability."
)


# ── Core data types ───────────────────────────────────────────────────────────

@dataclass(frozen=True)
class SecurityFinding:
    """A single heuristic security finding.

    Attributes
    ----------
    rule_id        : str   Identifier, e.g. ``"SEC001"``.
    risk_level     : str   ``HIGH``, ``MEDIUM``, or ``LOW``.
    title          : str   Short human-readable name.
    reason         : str   Why this specific node was flagged.
    explanation    : str   Plain-language description of the risk.
    recommendation : str   Actionable advice for the regex author.
    location       : tuple[int, int] | None
                           1-indexed ``(start_col, end_col)`` of the
                           triggering token in the original regex, or
                           ``None`` if position is unavailable.
    """

    rule_id:        str
    risk_level:     str
    title:          str
    reason:         str
    explanation:    str
    recommendation: str
    location:       tuple[int, int] | None = None

    def to_dict(self) -> dict:
        d: dict = {
            "rule_id":        self.rule_id,
            "risk_level":     self.risk_level,
            "title":          self.title,
            "reason":         self.reason,
            "explanation":    self.explanation,
            "recommendation": self.recommendation,
        }
        if self.location is not None:
            d["location"] = {"start": self.location[0], "end": self.location[1]}
        else:
            d["location"] = None
        return d


@dataclass(frozen=True)
class SecurityReport:
    """Aggregate security analysis result for one regex.

    Attributes
    ----------
    findings     : tuple[SecurityFinding, …]  All findings (may be empty).
    overall_risk : str                         Highest risk level found, or ``"NONE"``.
    caveat       : str                         Mandatory disclaimer about engine differences.
    """

    findings:     tuple[SecurityFinding, ...]
    overall_risk: str
    caveat:       str

    def to_dict(self) -> dict:
        return {
            "overall_risk": self.overall_risk,
            "findings":     [f.to_dict() for f in self.findings],
            "caveat":       self.caveat,
        }
