"""
Phase 6 — DFA Minimization tests.

Expected before/after counts (documented here and in docs/algorithms.md)
-------------------------------------------------------------------------

Pattern: (a|b)*abb
  Subset construction → 5 states.
  Our DFA is PARTIAL (no explicit dead state), so D0 and D2 are equivalent:
    D0 (start):    on 'a'→D1, on 'b'→D2
    D2 (after b):  on 'a'→D1, on 'b'→D2
  Same transitions, both non-accepting → Hopcroft merges them.
  Minimized 4-state DFA:
    0(=D0∪D2): 'a'→1, 'b'→0   1(=D1): 'a'→1, 'b'→2
    2(=D3):    'a'→1, 'b'→3   3(=D4): 'a'→1, 'b'→0  ← ACCEPTING
  NOTE: The Dragon Book's 5-state result assumes a COMPLETE DFA (with explicit
  dead state).  Our partial DFA removes that constraint and achieves 4 states.
  Result: 5 → 4, reduction 20.0%

Pattern: ab|cb
  Subset construction → 5 states
    D0(start) → D1(after a) → D3(accepting, after ab)
    D0(start) → D2(after c) → D4(accepting, after cb)
  D1 and D2: both have identical suffix language {b} → MERGED
  D3 and D4: both accepting with no outgoing transitions → MERGED
  Result: 5 → 3, reduction 40.0%

Pattern: a (literal)
  Subset construction → 2 states (start, accept)
  No merges possible.
  Result: 2 → 2, reduction 0.0%

Pattern: a*
  Subset construction → 1 state (start = accepting, self-loop on a)
  Nothing to merge.
  Result: 1 → 1, reduction 0.0%

Coverage targets
----------------
1.  minimized.states ≤ original.states  (always)
2.  Language equivalence: minimized and original agree on all test strings
3.  (a|b)*abb: stays at 5 states, 0.0% reduction
4.  ab|cb:     reduces 5→3 states, 40.0% reduction
5.  Start state always 0 after minimization
6.  Accepting states correct after minimization
7.  Stats: all fields present and correct values
8.  Stats: reduction_pct formula correct
9.  Unreachable state removal (manually constructed DFA)
10. to_dict() round-trip on both DFA and MinimizationStats
11. Determinism of transitions in minimized DFA
12. Alphabet preserved
13. No dead-state transitions in output (partial DFA maintained)
14. minimize_dfa is idempotent (minimize twice == minimize once)
"""

from __future__ import annotations

import json

import pytest

from app.dfa        import DFA, DFATransition, build_dfa, dfa_accepts
from app.nfa        import build_nfa, nfa_accepts
from app.optimizer  import MinimizationStats, minimize_dfa
from app.parser     import parse_pattern


# ── Helpers ───────────────────────────────────────────────────────────────────

def pipeline(pattern: str) -> tuple[DFA, DFA, MinimizationStats]:
    """Parse → NFA → DFA → minimized DFA."""
    nfa         = build_nfa(parse_pattern(pattern))
    dfa         = build_dfa(nfa)
    min_dfa, stats = minimize_dfa(dfa)
    return dfa, min_dfa, stats


def minimized(pattern: str) -> DFA:
    _, m, _ = pipeline(pattern)
    return m


def stats_for(pattern: str) -> MinimizationStats:
    _, _, s = pipeline(pattern)
    return s


# Shared battery of test strings for language-equivalence checks
_STRINGS = [
    "", "a", "b", "c",
    "ab", "ba", "aa", "bb", "cb",
    "abb", "aabb", "babb", "aba",
    "abba", "abbc", "abab",
    "0", "9", "abc",
]


# ─────────────────────────────────────────────────────────────────────────────
# 1. minimized_states ≤ original_states — always
# ─────────────────────────────────────────────────────────────────────────────

class TestMonotonicity:

    @pytest.mark.parametrize("pattern", [
        "a", "ab", "a|b", "a*", "a+", "a?",
        "(a|b)*", "(a|b)*abb",
        "[a-c]", "[0-9]+",
        "ab|cb",
    ])
    def test_minimized_never_larger(self, pattern):
        dfa, min_dfa, stats = pipeline(pattern)
        assert len(min_dfa.states) <= len(dfa.states), (
            f"Pattern {pattern!r}: minimized has MORE states "
            f"({len(min_dfa.states)}) than original ({len(dfa.states)})"
        )

    @pytest.mark.parametrize("pattern", [
        "a", "ab", "a|b", "a*", "a+", "a?",
        "(a|b)*", "(a|b)*abb",
        "[a-c]", "[0-9]+",
        "ab|cb",
    ])
    def test_stats_minimized_le_original(self, pattern):
        s = stats_for(pattern)
        assert s.minimized_states <= s.original_states


# ─────────────────────────────────────────────────────────────────────────────
# 2. Language equivalence
# ─────────────────────────────────────────────────────────────────────────────

class TestLanguageEquivalence:
    """Minimized DFA must accept exactly the same strings as the original."""

    @pytest.mark.parametrize("pattern", [
        "a",
        "ab",
        "a|b",
        "a*",
        "a+",
        "a?",
        "(a|b)*",
        "(a|b)*abb",
        "[a-c]",
        "[0-9]+",
        "ab|cb",
        "(ab|cb)*",
    ])
    def test_agrees_with_original_dfa(self, pattern):
        dfa, min_dfa, _ = pipeline(pattern)
        for s in _STRINGS:
            orig    = dfa_accepts(dfa, s)
            minimal = dfa_accepts(min_dfa, s)
            assert orig == minimal, (
                f"Pattern {pattern!r}: disagreement on {s!r} — "
                f"original={orig}, minimized={minimal}"
            )

    @pytest.mark.parametrize("pattern", [
        "a", "(a|b)*abb", "ab|cb",
    ])
    def test_agrees_with_nfa(self, pattern):
        """Three-way equivalence: NFA == original DFA == minimized DFA."""
        nfa             = build_nfa(parse_pattern(pattern))
        dfa             = build_dfa(nfa)
        min_dfa, _      = minimize_dfa(dfa)
        for s in _STRINGS:
            assert nfa_accepts(nfa, s) == dfa_accepts(min_dfa, s), (
                f"Pattern {pattern!r}: NFA ≠ minimized DFA on {s!r}"
            )


# ─────────────────────────────────────────────────────────────────────────────
# 3. (a|b)*abb — stays at 5 states, 0.0% reduction
# ─────────────────────────────────────────────────────────────────────────────

class TestCanonicalMinimization:
    """(a|b)*abb: partial DFA allows D0≡D2 to merge → 5→4 states (20% reduction).

    The Dragon Book's 5-state result assumes a COMPLETE DFA (with an explicit
    dead/trap state).  Our partial DFA omits the dead state, so D0 and D2 have
    identical transitions and are correctly merged by Hopcroft.
    """

    @pytest.fixture
    def result(self):
        return pipeline("(a|b)*abb")

    def test_original_has_five_states(self, result):
        dfa, _, _ = result
        assert len(dfa.states) == 5

    def test_minimized_has_four_states(self, result):
        # D0 ≡ D2 in partial DFA → merged → 4 states
        _, min_dfa, _ = result
        assert len(min_dfa.states) == 4

    def test_reduction_pct_twenty(self, result):
        _, _, stats = result
        assert stats.reduction_pct == 20.0

    def test_one_merged_by_hopcroft(self, result):
        _, _, stats = result
        assert stats.merged_by_hopcroft == 1

    def test_one_total_removed(self, result):
        _, _, stats = result
        assert stats.total_removed == 1

    def test_accepts_correct_strings_after_minimization(self, result):
        _, min_dfa, _ = result
        for s in ["abb", "aabb", "babb", "ababb"]:
            assert dfa_accepts(min_dfa, s)
        for s in ["", "ab", "abba", "abc"]:
            assert not dfa_accepts(min_dfa, s)

    def test_minimized_start_state_zero(self, result):
        _, min_dfa, _ = result
        assert min_dfa.start == 0

    def test_minimized_one_accepting_state(self, result):
        _, min_dfa, _ = result
        assert len(min_dfa.accepting) == 1

    def test_start_has_b_self_loop(self, result):
        """After merging D0 and D2, start state 0 must self-loop on 'b'."""
        _, min_dfa, _ = result
        from app.dfa.dfa import build_trans_map
        tm = build_trans_map(min_dfa)
        assert tm.get(min_dfa.start, {}).get("b") == min_dfa.start, (
            "Merged D0/D2 state must have a self-loop on 'b'"
        )


# ─────────────────────────────────────────────────────────────────────────────
# 4. ab|cb — 5 → 3 states, 40.0% reduction
# ─────────────────────────────────────────────────────────────────────────────

class TestMergeablePattern:
    """ab|cb: D1≡D2 (both see only 'b'→accept) and D3≡D4 (both accepting, no out)."""

    @pytest.fixture
    def result(self):
        return pipeline("ab|cb")

    def test_original_five_states(self, result):
        dfa, _, _ = result
        assert len(dfa.states) == 5

    def test_minimized_three_states(self, result):
        _, min_dfa, _ = result
        assert len(min_dfa.states) == 3

    def test_reduction_pct_40(self, result):
        _, _, stats = result
        assert stats.reduction_pct == 40.0

    def test_merged_by_hopcroft_is_two(self, result):
        # D1≡D2 → one merge, D3≡D4 → one merge, total 2 states removed
        _, _, stats = result
        assert stats.merged_by_hopcroft == 2

    def test_total_removed_is_two(self, result):
        _, _, stats = result
        assert stats.total_removed == 2

    def test_one_accepting_state(self, result):
        # D3 and D4 merge into one accepting state
        _, min_dfa, _ = result
        assert len(min_dfa.accepting) == 1

    def test_accepts_ab_and_cb(self, result):
        _, min_dfa, _ = result
        assert dfa_accepts(min_dfa, "ab")
        assert dfa_accepts(min_dfa, "cb")

    def test_rejects_others(self, result):
        _, min_dfa, _ = result
        for s in ["", "a", "b", "c", "ba", "bc", "abc", "acb"]:
            assert not dfa_accepts(min_dfa, s)


# ─────────────────────────────────────────────────────────────────────────────
# 5. Start state always 0
# ─────────────────────────────────────────────────────────────────────────────

class TestStartState:

    @pytest.mark.parametrize("pattern", [
        "a", "ab", "a|b", "a*", "(a|b)*abb", "ab|cb",
    ])
    def test_start_always_zero(self, pattern):
        assert minimized(pattern).start == 0

    @pytest.mark.parametrize("pattern", [
        "a", "ab", "a|b", "a*", "(a|b)*abb", "ab|cb",
    ])
    def test_start_in_states(self, pattern):
        m = minimized(pattern)
        assert m.start in m.states


# ─────────────────────────────────────────────────────────────────────────────
# 6. Accepting states correct
# ─────────────────────────────────────────────────────────────────────────────

class TestAccepting:

    def test_literal_has_one_accepting(self):
        assert len(minimized("a").accepting) == 1

    def test_star_start_is_accepting(self):
        m = minimized("a*")
        assert m.start in m.accepting

    def test_canonical_has_one_accepting(self):
        assert len(minimized("(a|b)*abb").accepting) == 1

    def test_accepting_subset_of_states(self):
        m = minimized("(a|b)*abb")
        assert m.accepting.issubset(m.states)


# ─────────────────────────────────────────────────────────────────────────────
# 7 & 8. MinimizationStats: fields and formula
# ─────────────────────────────────────────────────────────────────────────────

class TestStats:

    def test_all_fields_present(self):
        s = stats_for("(a|b)*abb")
        d = s.to_dict()
        expected_keys = {
            "original_states", "reachable_states", "minimized_states",
            "removed_unreachable", "merged_by_hopcroft",
            "total_removed", "reduction_pct",
        }
        assert set(d.keys()) == expected_keys

    def test_total_removed_formula(self):
        s = stats_for("ab|cb")
        assert s.total_removed == s.original_states - s.minimized_states

    def test_reduction_pct_formula(self):
        s = stats_for("ab|cb")
        expected = round((s.original_states - s.minimized_states) / s.original_states * 100, 2)
        assert s.reduction_pct == expected

    def test_removed_unreachable_plus_merged_equals_total(self):
        s = stats_for("ab|cb")
        assert s.removed_unreachable + s.merged_by_hopcroft == s.total_removed

    def test_json_round_trip(self):
        s = stats_for("(a|b)*abb")
        d = s.to_dict()
        loaded = json.loads(json.dumps(d))
        assert loaded["original_states"]  == 5
        assert loaded["minimized_states"] == 4   # partial DFA: D0≡D2 merged
        assert loaded["reduction_pct"]    == 20.0

    @pytest.mark.parametrize("pattern,expected_orig,expected_min,expected_pct", [
        # partial DFA: D0≡D2 in (a|b)*abb → 5→4 (20%)
        ("(a|b)*abb", 5, 4, 20.0),
        # D1≡D2 and D3≡D4 in ab|cb → 5→3 (40%)
        ("ab|cb",     5, 3, 40.0),
    ])
    def test_known_stats_values(self, pattern, expected_orig, expected_min, expected_pct):
        s = stats_for(pattern)
        assert s.original_states  == expected_orig
        assert s.minimized_states == expected_min
        assert s.reduction_pct    == expected_pct


# ─────────────────────────────────────────────────────────────────────────────
# 9. Unreachable state removal
# ─────────────────────────────────────────────────────────────────────────────

class TestUnreachableRemoval:

    @pytest.fixture
    def dfa_with_unreachable(self) -> DFA:
        """Hand-crafted DFA with state 99 that is unreachable from start (0)."""
        return DFA(
            states      = frozenset({0, 1, 99}),
            alphabet    = frozenset({"a"}),
            transitions = (
                DFATransition(0, "a", 1),
                DFATransition(99, "a", 1),   # 99 has outgoing but is unreachable
            ),
            start       = 0,
            accepting   = frozenset({1}),
        )

    def test_unreachable_removed(self, dfa_with_unreachable):
        min_dfa, stats = minimize_dfa(dfa_with_unreachable)
        assert 99 not in min_dfa.states

    def test_removed_unreachable_count(self, dfa_with_unreachable):
        _, stats = minimize_dfa(dfa_with_unreachable)
        assert stats.removed_unreachable == 1

    def test_language_preserved_after_removal(self, dfa_with_unreachable):
        min_dfa, _ = minimize_dfa(dfa_with_unreachable)
        assert dfa_accepts(min_dfa, "a")
        assert not dfa_accepts(min_dfa, "")
        assert not dfa_accepts(min_dfa, "aa")


# ─────────────────────────────────────────────────────────────────────────────
# 10. to_dict() round-trips
# ─────────────────────────────────────────────────────────────────────────────

class TestToDict:

    def test_dfa_to_dict_after_minimize(self):
        m = minimized("(a|b)*abb")
        d = m.to_dict()
        assert set(d.keys()) == {"states", "alphabet", "transitions", "start", "accepting"}
        assert d["start"] == 0

    def test_json_serialisable(self):
        m = minimized("ab|cb")
        json.dumps(m.to_dict())   # must not raise

    def test_stats_to_dict_json_serialisable(self):
        s = stats_for("ab|cb")
        json.dumps(s.to_dict())


# ─────────────────────────────────────────────────────────────────────────────
# 11. Determinism of output
# ─────────────────────────────────────────────────────────────────────────────

class TestDeterminism:

    @pytest.mark.parametrize("pattern", [
        "a", "(a|b)*abb", "ab|cb",
    ])
    def test_at_most_one_transition_per_state_symbol(self, pattern):
        m    = minimized(pattern)
        seen: set[tuple[int, str]] = set()
        for t in m.transitions:
            key = (t.from_id, t.symbol)
            assert key not in seen, (
                f"Non-deterministic minimized DFA: state {t.from_id} "
                f"has two transitions on '{t.symbol}'"
            )
            seen.add(key)

    def test_minimize_twice_is_stable(self):
        """minimize(minimize(dfa)) should give same state count as minimize(dfa)."""
        dfa             = build_dfa(build_nfa(parse_pattern("ab|cb")))
        min1, stats1    = minimize_dfa(dfa)
        min2, stats2    = minimize_dfa(min1)
        assert len(min2.states) == len(min1.states)
        assert stats2.minimized_states == stats1.minimized_states


# ─────────────────────────────────────────────────────────────────────────────
# 12. Alphabet preserved
# ─────────────────────────────────────────────────────────────────────────────

class TestAlphabet:

    @pytest.mark.parametrize("pattern", [
        "a", "ab|cb", "(a|b)*abb",
    ])
    def test_alphabet_unchanged(self, pattern):
        dfa, min_dfa, _ = pipeline(pattern)
        assert min_dfa.alphabet == dfa.alphabet


# ─────────────────────────────────────────────────────────────────────────────
# 13. No dead-state transitions (partial DFA maintained)
# ─────────────────────────────────────────────────────────────────────────────

class TestNoDeadTransitions:

    @pytest.mark.parametrize("pattern", [
        "a", "ab|cb", "(a|b)*abb",
    ])
    def test_all_transition_targets_in_states(self, pattern):
        m = minimized(pattern)
        for t in m.transitions:
            assert t.to_id in m.states, (
                f"Transition target {t.to_id} is not in states {m.states}"
            )

    @pytest.mark.parametrize("pattern", [
        "a", "ab|cb", "(a|b)*abb",
    ])
    def test_all_transition_sources_in_states(self, pattern):
        m = minimized(pattern)
        for t in m.transitions:
            assert t.from_id in m.states


# ─────────────────────────────────────────────────────────────────────────────
# 14. Idempotency
# ─────────────────────────────────────────────────────────────────────────────

class TestIdempotency:

    @pytest.mark.parametrize("pattern", [
        "a", "ab|cb", "(a|b)*abb", "[a-z]+",
    ])
    def test_second_minimize_no_further_reduction(self, pattern):
        dfa          = build_dfa(build_nfa(parse_pattern(pattern)))
        min1, _      = minimize_dfa(dfa)
        min2, stats2 = minimize_dfa(min1)
        assert len(min2.states) == len(min1.states), (
            f"Pattern {pattern!r}: second minimization reduced further "
            f"({len(min1.states)} → {len(min2.states)}); "
            "output is not already minimal"
        )
        assert stats2.reduction_pct == 0.0
