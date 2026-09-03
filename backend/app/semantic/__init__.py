"""
Semantic analysis package — public API.

Usage
-----
    from app.semantic import analyze, has_errors, Diagnostic, Severity

    diagnostics = analyze(ast)
    if has_errors(diagnostics):
        for d in diagnostics:
            print(d.to_dict())
"""

from app.semantic.diagnostic import Diagnostic, Severity
from app.semantic.analyzer  import analyze, has_errors

__all__ = ["analyze", "has_errors", "Diagnostic", "Severity"]
