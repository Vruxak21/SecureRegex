"""
DFA package — public API.

Usage
-----
    from app.dfa import build_dfa, dfa_accepts, DFA, DFATransition

    dfa = build_dfa(nfa)
    ok  = dfa_accepts(dfa, "abb")
    print(dfa.to_dict())
"""

from app.dfa.dfa    import DFA, DFATransition, dfa_accepts, build_trans_map
from app.dfa.subset import build_dfa

__all__ = [
    "DFA",
    "DFATransition",
    "dfa_accepts",
    "build_trans_map",
    "build_dfa",
]
