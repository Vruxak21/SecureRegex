"""
NFA package — public API.

Usage
-----
    from app.nfa import build_nfa, nfa_accepts, NFA, Transition

    nfa = build_nfa(ast)
    ok  = nfa_accepts(nfa, "abb")
    print(nfa.to_dict())
"""

from app.nfa.nfa       import NFA, Transition, EPSILON, epsilon_closure, nfa_accepts
from app.nfa.thompson  import build_nfa, NFABuildError

__all__ = [
    "NFA",
    "Transition",
    "EPSILON",
    "epsilon_closure",
    "nfa_accepts",
    "build_nfa",
    "NFABuildError",
]
