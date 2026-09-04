"""
Security package — public API.

Usage
-----
    from app.security import analyze_security, SecurityReport, SecurityFinding
    from app.security import HIGH, MEDIUM, LOW, NONE

    report = analyze_security(ast)
    print(report.to_dict())
"""

from app.security.report   import (
    SecurityFinding, SecurityReport,
    HIGH, MEDIUM, LOW, NONE, CAVEAT,
)
from app.security.analyzer import analyze_security

__all__ = [
    "analyze_security",
    "SecurityFinding",
    "SecurityReport",
    "HIGH",
    "MEDIUM",
    "LOW",
    "NONE",
    "CAVEAT",
]
