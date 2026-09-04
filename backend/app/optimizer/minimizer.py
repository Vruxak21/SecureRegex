"""
DFA Minimization — Hopcroft's algorithm + unreachable-state removal.

Algorithm choice: **Hopcroft's partition-refinement** (O(n log n))
---------------------------------------------------------------
We chose Hopcroft over the simpler O(n²) table-filling (Myhill-Nerode) method
because:
  1. It handles large DFAs from complex char-class patterns efficiently.
  2. It is the industry-standard algorithm and worth documenting academically.
  3. The implementation complexity is manageable (≈ 80 lines).

See docs/algorithms.md §Phase 6 for the full derivation and trace.

Public API
----------
    minimize_dfa(dfa: DFA) -> tuple[DFA, MinimizationStats]

    Returns the minimized DFA (same JSON-serialisable shape) and a stats
    object with before/after state counts and reduction percentage.
"""

from __future__ import annotations

from collections import deque
from dataclasses  import dataclass

from app.dfa.dfa    import DFA, DFATransition, build_trans_map


# ── Statistics ────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class MinimizationStats:
    """Before/after statistics for a single minimization run.

    Attributes
    ----------
    original_states      : int   States in the input DFA.
    reachable_states     : int   After removing unreachable states.
    minimized_states     : int   After Hopcroft partition refinement.
    removed_unreachable  : int   ``original - reachable``.
    merged_by_hopcroft   : int   ``reachable - minimized``.
    total_removed        : int   ``original - minimized``.
    reduction_pct        : float Percentage reduction vs. original.
    """

    original_states:     int
    reachable_states:    int
    minimized_states:    int
    removed_unreachable: int
    merged_by_hopcroft:  int
    total_removed:       int
    reduction_pct:       float

    def to_dict(self) -> dict:
        return {
            "original_states":     self.original_states,
            "reachable_states":    self.reachable_states,
            "minimized_states":    self.minimized_states,
            "removed_unreachable": self.removed_unreachable,
            "merged_by_hopcroft":  self.merged_by_hopcroft,
            "total_removed":       self.total_removed,
            "reduction_pct":       self.reduction_pct,
        }


# ── Step 1: Remove unreachable states ────────────────────────────────────────

def _remove_unreachable(dfa: DFA) -> DFA:
    """BFS from start state; return a DFA containing only reachable states."""
    reachable: set[int] = set()
    queue: deque[int]   = deque([dfa.start])
    tm = build_trans_map(dfa)

    while queue:
        s = queue.popleft()
        if s in reachable:
            continue
        reachable.add(s)
        for dest in tm.get(s, {}).values():
            if dest not in reachable:
                queue.append(dest)

    if reachable == dfa.states:
        return dfa                          # nothing to trim

    return DFA(
        states      = frozenset(reachable),
        alphabet    = dfa.alphabet,
        transitions = tuple(
            t for t in dfa.transitions
            if t.from_id in reachable and t.to_id in reachable
        ),
        start       = dfa.start,
        accepting   = dfa.accepting & reachable,
    )


# ── Step 2: Hopcroft's algorithm ──────────────────────────────────────────────

def _hopcroft(dfa: DFA) -> DFA:
    """Minimize *dfa* via Hopcroft's partition-refinement algorithm.

    The algorithm operates on the **completed** DFA (with an explicit dead/trap
    state).  The dead partition is excluded when rebuilding the output DFA,
    so the returned DFA is still a partial DFA (no dead state).
    """
    if len(dfa.states) <= 1:
        return dfa

    # ── Complete the DFA with an explicit dead state ──────────────────────
    dead: int = max(dfa.states) + 1
    all_states: frozenset[int] = dfa.states | frozenset({dead})
    alphabet = dfa.alphabet

    tm = build_trans_map(dfa)

    def delta(s: int, a: str) -> int:
        if s == dead:
            return dead
        return tm.get(s, {}).get(a, dead)

    # ── Precompute reverse-transition map ─────────────────────────────────
    # rev[a][d] = set of states that go to d on symbol a
    rev: dict[str, dict[int, set[int]]] = {
        a: {s: set() for s in all_states} for a in alphabet
    }
    for s in all_states:
        for a in alphabet:
            rev[a][delta(s, a)].add(s)

    # ── Initial partition: {F, Q \ F} (drop empty sets) ──────────────────
    F   = frozenset(dfa.accepting)
    QF  = frozenset(all_states - dfa.accepting)

    partition: set[frozenset[int]] = set()
    if F:   partition.add(F)
    if QF:  partition.add(QF)

    # Seed worklist with both initial blocks (correct & simple)
    worklist: set[frozenset[int]] = set(partition)

    # ── Refinement loop ───────────────────────────────────────────────────
    while worklist:
        W = next(iter(worklist))
        worklist.discard(W)

        for a in alphabet:
            # X = states whose a-transition lands in W
            X: frozenset[int] = frozenset().union(*(rev[a][w] for w in W))
            if not X:
                continue

            next_partition: set[frozenset[int]] = set()
            for Y in partition:
                inter = Y & X
                diff  = Y - X
                if inter and diff:
                    i_f = frozenset(inter)
                    d_f = frozenset(diff)
                    next_partition.add(i_f)
                    next_partition.add(d_f)
                    if Y in worklist:
                        worklist.discard(Y)
                        worklist.add(i_f)
                        worklist.add(d_f)
                    else:
                        # Hopcroft optimisation: enqueue the smaller half
                        worklist.add(i_f if len(i_f) <= len(d_f) else d_f)
                else:
                    next_partition.add(Y)
            partition = next_partition

    # ── Build state mapping ───────────────────────────────────────────────
    state_to_block: dict[int, frozenset[int]] = {}
    for block in partition:
        for s in block:
            state_to_block[s] = block

    dead_block  = state_to_block[dead]
    start_block = state_to_block[dfa.start]

    # Live blocks sorted: start block first, then by min-state-ID for stability
    live_blocks: list[frozenset[int]] = sorted(
        (b for b in partition if b != dead_block),
        key=lambda b: (b != start_block, min(b)),
    )

    block_to_id: dict[frozenset[int], int] = {}
    for idx, block in enumerate(live_blocks):
        block_to_id[block] = idx          # start block → 0 guaranteed

    # ── Reconstruct the minimized DFA ─────────────────────────────────────
    new_transitions: list[DFATransition] = []
    for block in live_blocks:
        # Pick any representative from this block (all are equivalent)
        rep   = next(iter(block))
        f_id  = block_to_id[block]
        for a in sorted(alphabet):
            dest_block = state_to_block[delta(rep, a)]
            if dest_block == dead_block:
                continue                   # omit dead transitions (partial DFA)
            new_transitions.append(DFATransition(f_id, a, block_to_id[dest_block]))

    new_accepting = frozenset(
        block_to_id[b] for b in live_blocks if b & dfa.accepting
    )

    return DFA(
        states      = frozenset(block_to_id.values()),
        alphabet    = dfa.alphabet,
        transitions = tuple(new_transitions),
        start       = 0,
        accepting   = new_accepting,
    )


# ── Public API ─────────────────────────────────────────────────────────────────

def minimize_dfa(dfa: DFA) -> tuple[DFA, MinimizationStats]:
    """Minimize *dfa* and return *(minimized_dfa, stats)*.

    Two-phase process:
    1. Remove states not reachable from the start state (BFS).
    2. Merge indistinguishable states via Hopcroft's algorithm.

    Parameters
    ----------
    dfa : DFA
        Input DFA (typically from :func:`app.dfa.build_dfa`).

    Returns
    -------
    tuple[DFA, MinimizationStats]
        ``minimized_dfa`` — equivalent DFA with fewest possible states.
        ``stats``         — before/after counts and reduction percentage.

    Notes
    -----
    * The minimized DFA has the same JSON-serialisable shape as the input.
    * Start state is always ID 0.
    * The output is a canonical minimal DFA; all reachable states are
      distinguishable (no two states accept the same suffix language).
    * Language equivalence is preserved: for every string s,
      ``dfa_accepts(minimized, s) == dfa_accepts(original, s)``.
    """
    original_count = len(dfa.states)

    # Phase 1 — unreachable removal
    reachable_dfa   = _remove_unreachable(dfa)
    reachable_count = len(reachable_dfa.states)

    # Phase 2 — Hopcroft minimisation
    min_dfa         = _hopcroft(reachable_dfa)
    minimized_count = len(min_dfa.states)

    reduction = (
        (original_count - minimized_count) / original_count * 100
        if original_count > 0 else 0.0
    )

    stats = MinimizationStats(
        original_states     = original_count,
        reachable_states    = reachable_count,
        minimized_states    = minimized_count,
        removed_unreachable = original_count - reachable_count,
        merged_by_hopcroft  = reachable_count - minimized_count,
        total_removed       = original_count - minimized_count,
        reduction_pct       = round(reduction, 2),
    )

    return min_dfa, stats
