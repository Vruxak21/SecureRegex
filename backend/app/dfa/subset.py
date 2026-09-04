"""
Subset Construction — NFA to DFA conversion.

Algorithm (standard powerset construction)
-------------------------------------------
1.  Compute D0 = ε-closure({nfa.start}) — the start DFA state.
2.  Maintain a worklist of DFA states (sets of NFA states) not yet processed.
3.  For each unprocessed DFA state S and each symbol a in the alphabet:
        T = ε-closure( {q | p ∈ S, (p, a, q) ∈ nfa.transitions} )
        If T is non-empty and not yet a DFA state, add it to the worklist.
        Record transition S --a--> T.
4.  A DFA state is accepting iff it contains any NFA accepting state.
5.  Stop when the worklist is empty.

Blowup guard
------------
If the number of DFA states reaches ``max_states`` during construction, a
:class:`app.exceptions.DFAConstructionError` is raised immediately instead of
hanging.  The default limit comes from ``settings.max_dfa_states``.

Partial DFA (no dead state)
---------------------------
Missing transitions (where T is empty) are simply omitted — this keeps the
DFA smaller.  :func:`app.dfa.dfa.dfa_accepts` treats a missing transition as
an implicit rejection.

State numbering
---------------
DFA states are assigned IDs in BFS discovery order, so the start state is
always **0**.  This is stable and predictable for tests.
"""

from __future__ import annotations

from collections import deque

from app.config     import settings as _default_settings
from app.exceptions import DFAConstructionError
from app.nfa        import NFA, epsilon_closure
from app.nfa.nfa    import build_eps_map, build_sym_map
from app.dfa.dfa    import DFA, DFATransition


def build_dfa(
    nfa:        NFA,
    max_states: int | None = None,
) -> DFA:
    """Convert *nfa* to an equivalent DFA via subset construction.

    Parameters
    ----------
    nfa        : NFA
        Source NFA (output of :func:`app.nfa.build_nfa`).
    max_states : int | None
        Maximum number of DFA states to create.  Defaults to
        ``settings.max_dfa_states``.  Pass a smaller value in tests.

    Returns
    -------
    DFA
        Equivalent deterministic automaton.

    Raises
    ------
    DFAConstructionError
        If the number of generated DFA states exceeds *max_states*.
    """
    if max_states is None:
        max_states = _default_settings.max_dfa_states

    # ── Pre-compute NFA lookup structures ────────────────────────────────
    eps_map = build_eps_map(nfa)
    sym_map = build_sym_map(nfa)

    # ── Initialise with the start DFA state ──────────────────────────────
    start_nfa_set: frozenset[int] = epsilon_closure(eps_map, {nfa.start})

    # Mapping: frozenset[NFA states] → DFA state ID (BFS order → start = 0)
    dfa_id_map: dict[frozenset[int], int] = {start_nfa_set: 0}

    # BFS worklist
    worklist: deque[frozenset[int]] = deque([start_nfa_set])

    # Collected transitions
    transitions: list[DFATransition] = []

    # ── BFS over DFA states ───────────────────────────────────────────────
    while worklist:
        nfa_set  = worklist.popleft()
        dfa_from = dfa_id_map[nfa_set]

        for symbol in sorted(nfa.alphabet):   # sorted → deterministic output
            # Compute successor NFA states
            next_nfa: set[int] = set()
            for nfa_state in nfa_set:
                for dest in sym_map.get(nfa_state, {}).get(symbol, ()):
                    next_nfa.add(dest)

            if not next_nfa:
                continue                       # missing → implicit dead state

            next_set = epsilon_closure(eps_map, next_nfa)

            if next_set not in dfa_id_map:
                if len(dfa_id_map) >= max_states:
                    raise DFAConstructionError(
                        f"Subset construction aborted: DFA state count reached "
                        f"the configured limit of {max_states}. "
                        "The pattern is too complex to compile safely.",
                        detail=(
                            "Increase SECUREREGEX_MAX_DFA_STATES or simplify "
                            "the regular expression."
                        ),
                    )
                dfa_id_map[next_set] = len(dfa_id_map)
                worklist.append(next_set)

            transitions.append(DFATransition(dfa_from, symbol, dfa_id_map[next_set]))

    # ── Determine accepting DFA states ────────────────────────────────────
    accepting = frozenset(
        dfa_id
        for nfa_set, dfa_id in dfa_id_map.items()
        if nfa_set & nfa.accepting       # any NFA accepting state in set
    )

    return DFA(
        states      = frozenset(dfa_id_map.values()),
        alphabet    = nfa.alphabet,
        transitions = tuple(transitions),
        start       = 0,
        accepting   = accepting,
    )
