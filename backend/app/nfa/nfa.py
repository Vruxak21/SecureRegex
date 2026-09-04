"""
NFA dataclass and simulation engine.

This module owns:
  * ``Transition``  – a single labelled edge (symbol=None means ε)
  * ``NFA``         – the immutable NFA value object (frozen dataclass)
  * ``epsilon_closure`` – standard ε-closure computation
  * ``nfa_accepts``     – subset-construction simulation with step guard
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from app.config import settings as _default_settings
from app.exceptions import SimulationTimeoutError

# Sentinel for ε-transitions (use ``None`` throughout the codebase)
EPSILON: None = None


# ── Core data types ───────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Transition:
    """A single labelled edge in the NFA.

    Attributes
    ----------
    from_id : int
        Source state ID.
    symbol  : str | None
        The character that triggers this transition.
        ``None`` (= :data:`EPSILON`) denotes an ε-transition.
    to_id   : int
        Destination state ID.
    """

    from_id: int
    symbol:  str | None   # None → ε
    to_id:   int

    def __repr__(self) -> str:  # pragma: no cover
        sym = "ε" if self.symbol is None else repr(self.symbol)
        return f"Transition({self.from_id} --{sym}--> {self.to_id})"


@dataclass(frozen=True)
class NFA:
    """An immutable Non-deterministic Finite Automaton.

    Built by Thompson's construction in :mod:`app.nfa.thompson`.
    Uses ``frozenset`` / ``tuple`` so the whole object is hashable.

    Attributes
    ----------
    states      : frozenset[int]        All state IDs.
    alphabet    : frozenset[str]        Non-ε symbols that appear in transitions.
    transitions : tuple[Transition, …]  All edges (symbol and ε).
    start       : int                   Start state ID.
    accepting   : frozenset[int]        Set of accepting state IDs.
    """

    states:      frozenset[int]
    alphabet:    frozenset[str]
    transitions: tuple[Transition, ...]
    start:       int
    accepting:   frozenset[int]

    # ── Convenience views ──────────────────────────────────────────────────

    @property
    def epsilon_transitions(self) -> tuple[Transition, ...]:
        """All ε-transitions (symbol is None)."""
        return tuple(t for t in self.transitions if t.symbol is None)

    @property
    def symbol_transitions(self) -> tuple[Transition, ...]:
        """All non-ε transitions."""
        return tuple(t for t in self.transitions if t.symbol is not None)

    # ── Serialisation ──────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        """Return a JSON-serialisable dict suitable for the frontend visualiser.

        ε-transitions are represented as ``"symbol": "ε"`` (not null) so that
        React Flow can display them without special-casing.
        """
        return {
            "states": sorted(self.states),
            "alphabet": sorted(self.alphabet),
            "transitions": [
                {
                    "from":   t.from_id,
                    "symbol": "ε" if t.symbol is None else t.symbol,
                    "to":     t.to_id,
                }
                for t in sorted(
                    self.transitions,
                    key=lambda t: (t.from_id, t.symbol or "\x00", t.to_id),
                )
            ],
            "start":     self.start,
            "accepting": sorted(self.accepting),
        }


# ── ε-closure ─────────────────────────────────────────────────────────────────

def epsilon_closure(
    eps_map: dict[int, list[int]],
    states:  Iterable[int],
) -> frozenset[int]:
    """Compute the ε-closure of *states* using a precomputed adjacency map.

    Parameters
    ----------
    eps_map : dict[int, list[int]]
        Mapping from each state to the list of states reachable via a single ε.
        Build it once per NFA with :func:`build_eps_map`.
    states  : Iterable[int]
        Seed set of states.

    Returns
    -------
    frozenset[int]
        All states reachable from *states* via zero or more ε-transitions.
    """
    closure: set[int] = set(states)
    stack: list[int]  = list(closure)
    while stack:
        s = stack.pop()
        for t in eps_map.get(s, ()):
            if t not in closure:
                closure.add(t)
                stack.append(t)
    return frozenset(closure)


def build_eps_map(nfa: NFA) -> dict[int, list[int]]:
    """Precompute the ε-adjacency map for *nfa* (call once before simulation)."""
    eps: dict[int, list[int]] = {s: [] for s in nfa.states}
    for t in nfa.transitions:
        if t.symbol is None:
            eps[t.from_id].append(t.to_id)
    return eps


def build_sym_map(nfa: NFA) -> dict[int, dict[str, list[int]]]:
    """Precompute the symbol-transition map for *nfa* (call once before simulation)."""
    sym: dict[int, dict[str, list[int]]] = {s: {} for s in nfa.states}
    for t in nfa.transitions:
        if t.symbol is not None:
            sym[t.from_id].setdefault(t.symbol, []).append(t.to_id)
    return sym


# ── NFA simulation ────────────────────────────────────────────────────────────

def nfa_accepts(
    nfa:       NFA,
    string:    str,
    max_steps: int | None = None,
) -> bool:
    """Simulate *nfa* on *string* using the standard ε-closure + BFS algorithm.

    Parameters
    ----------
    nfa       : NFA          The automaton to simulate.
    string    : str          Input string.
    max_steps : int | None   Maximum number of (state, char) processing steps.
                             Defaults to ``Settings.max_computation_steps``.

    Returns
    -------
    bool
        True if *nfa* accepts *string*.

    Raises
    ------
    SimulationTimeoutError
        If the number of processing steps exceeds *max_steps*.  This prevents
        pathologically large NFAs from hanging the server.
    """
    if max_steps is None:
        max_steps = _default_settings.max_computation_steps

    eps_map = build_eps_map(nfa)
    sym_map = build_sym_map(nfa)

    current: frozenset[int] = epsilon_closure(eps_map, {nfa.start})
    steps   = 0

    for char in string:
        steps += len(current)
        if steps > max_steps:
            raise SimulationTimeoutError(
                f"NFA simulation exceeded {max_steps} steps on input "
                f"of length {len(string)}.",
                detail=(
                    "The pattern may have exponential ambiguity. "
                    "Consider simplifying it or increasing the limit via "
                    "SECUREREGEX_MAX_COMPUTATION_STEPS."
                ),
            )

        next_states: set[int] = set()
        for state in current:
            for dest in sym_map.get(state, {}).get(char, ()):
                next_states.add(dest)

        current = epsilon_closure(eps_map, next_states)

    return bool(current & nfa.accepting)
