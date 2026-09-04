"""
DFA dataclass and deterministic simulation engine.

Exports
-------
DFATransition  – a single labelled edge  (no ε-transitions in a DFA)
DFA            – immutable DFA value object
build_trans_map – build a fast dict lookup from the transitions tuple
dfa_accepts    – O(|string|) simulation using the prebuilt map
"""

from __future__ import annotations

from typing    import NamedTuple
from dataclasses import dataclass


# ── Core data types ───────────────────────────────────────────────────────────

class DFATransition(NamedTuple):
    """A single deterministic edge in the DFA.

    Unlike NFA transitions there is no ε variant — every edge is labelled
    with exactly one character from the effective alphabet.

    Attributes
    ----------
    from_id : int   Source DFA state.
    symbol  : str   Input character triggering the transition.
    to_id   : int   Destination DFA state.
    """

    from_id: int
    symbol:  str
    to_id:   int


@dataclass(frozen=True)
class DFA:
    """An immutable Deterministic Finite Automaton.

    Built by subset construction in :mod:`app.dfa.subset`.

    DFA states are numbered 0, 1, 2, … with state **0** always being the
    start state.  Each DFA state corresponds to a *frozenset* of NFA states
    (the subset used during construction is not stored here to keep the
    dataclass lean).

    Attributes
    ----------
    states      : frozenset[int]            All DFA state IDs.
    alphabet    : frozenset[str]            Symbols present in transitions.
    transitions : tuple[DFATransition, …]  All deterministic edges.
    start       : int                       Always 0.
    accepting   : frozenset[int]            Accepting DFA states.
    """

    states:      frozenset[int]
    alphabet:    frozenset[str]
    transitions: tuple[DFATransition, ...]
    start:       int
    accepting:   frozenset[int]

    # ── Derived views ──────────────────────────────────────────────────────

    def is_complete(self) -> bool:
        """True if every (state, symbol) pair has exactly one transition."""
        expected = len(self.states) * len(self.alphabet)
        return len(self.transitions) == expected

    # ── Serialisation ──────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        """Return a JSON-serialisable dict compatible with the frontend
        visualiser (same shape as ``NFA.to_dict()``)."""
        return {
            "states": sorted(self.states),
            "alphabet": sorted(self.alphabet),
            "transitions": [
                {"from": t.from_id, "symbol": t.symbol, "to": t.to_id}
                for t in sorted(self.transitions, key=lambda t: (t.from_id, t.symbol))
            ],
            "start":     self.start,
            "accepting": sorted(self.accepting),
        }


# ── Simulation helpers ────────────────────────────────────────────────────────

def build_trans_map(dfa: DFA) -> dict[int, dict[str, int]]:
    """Precompute ``{state: {symbol: dest_state}}`` for O(1) lookup.

    Call once before a batch of :func:`dfa_accepts` calls to amortise the
    construction cost.
    """
    trans: dict[int, dict[str, int]] = {s: {} for s in dfa.states}
    for t in dfa.transitions:
        trans[t.from_id][t.symbol] = t.to_id
    return trans


# ── DFA simulation ────────────────────────────────────────────────────────────

def dfa_accepts(
    dfa:    DFA,
    string: str,
    *,
    trans_map: dict[int, dict[str, int]] | None = None,
) -> bool:
    """Simulate *dfa* on *string* in O(|string|) time.

    Parameters
    ----------
    dfa       : DFA
        The automaton to simulate.
    string    : str
        Input string.
    trans_map : dict | None
        Precomputed transition map from :func:`build_trans_map`.
        Pass this when calling ``dfa_accepts`` in a tight loop to avoid
        rebuilding the map on every call.

    Returns
    -------
    bool
        True if *dfa* accepts *string*.
    """
    if trans_map is None:
        trans_map = build_trans_map(dfa)

    current = dfa.start
    for char in string:
        row = trans_map.get(current)
        if row is None or char not in row:
            return False        # dead / missing transition → reject
        current = row[char]

    return current in dfa.accepting
