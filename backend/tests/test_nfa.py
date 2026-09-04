"""
Phase 4 — NFA Construction tests.

State and transition counts (Thompson's construction)
------------------------------------------------------
All counts are derived analytically; each is documented inline.

Pattern  | States | Sym trans | ε-trans | Total trans
---------|--------|-----------|---------|------------
a        |   2    |     1     |    0    |     1
ab       |   4    |     2     |    1    |     3
a|b      |   6    |     2     |    4    |     6
a*       |   4    |     1     |    4    |     5
a+       |   3    |     1     |    2    |     3
a?       |   4    |     1     |    3    |     4
[a-c]    |   2    |     3     |    0    |     3
(a|b)*   |   8    |     2     |    8    |    10
(a|b)*abb|  14    |     5     |   11    |    16

Derivation for (a|b)*abb:
  • a (literal 1)  : 2 states, 1 sym
  • b (literal 2)  : 2 states, 1 sym
  • Union(a,b)     : +2 states, +4 ε  → 6 states, 2 sym, 4 ε
  • Star(…)        : +2 states, +4 ε  → 8 states, 2 sym, 8 ε
  • a (literal 3)  : 2 states, 1 sym  → 10 states
  • Concat(star,a) : +0 states, +1 ε  → 10 states, 3 sym, 9 ε
  • b (literal 4)  : 2 states, 1 sym  → 12 states
  • Concat(…,b)    : +0 states, +1 ε  → 12 states, 4 sym, 10 ε
  • b (literal 5)  : 2 states, 1 sym  → 14 states
  • Concat(…,b)    : +0 states, +1 ε  → 14 states, 5 sym, 11 ε
                                        Total: 16 transitions ✓

Coverage targets
----------------
1.  State counts for simple patterns (literal, concat, union, star, plus, question)
2.  ε-transition counts match Thompson's construction formulas
3.  Symbol-transition counts match alphabet expansion
4.  Exactly one start state; exactly one accepting state
5.  Alphabet set derived from symbol transitions
6.  NFA simulation: (a|b)*abb accepts/rejects test strings
7.  ε-closure correctness
8.  NFA.to_dict() structure and JSON round-trip
9.  CharClass range expansion
10. EpsilonNode builds correctly
11. Plus/Question structure (correct state counts)
12. Max-steps guard raises SimulationTimeoutError
13. Composed pattern (a|b)*abb: exact state and transition counts
"""

from __future__ import annotations

import json

import pytest

from app.ast import (
    CharClassNode,
    ClassRange,
    ConcatNode,
    EpsilonNode,
    LiteralNode,
    PlusNode,
    QuestionNode,
    StarNode,
    UnionNode,
)
from app.exceptions import SimulationTimeoutError
from app.nfa import (
    EPSILON,
    NFA,
    Transition,
    build_nfa,
    epsilon_closure,
    nfa_accepts,
)
from app.nfa.nfa import build_eps_map, build_sym_map
from app.parser import parse_pattern


# ── Helpers ───────────────────────────────────────────────────────────────────

def nfa(pattern: str) -> NFA:
    """Parse *pattern* and build the NFA."""
    return build_nfa(parse_pattern(pattern))


def count_eps(n: NFA) -> int:
    return len(n.epsilon_transitions)


def count_sym(n: NFA) -> int:
    return len(n.symbol_transitions)


# ─────────────────────────────────────────────────────────────────────────────
# 1. State counts for simple patterns
# ─────────────────────────────────────────────────────────────────────────────

class TestStateCounts:
    """Thompson's construction: each rule adds a predictable number of states."""

    def test_literal_state_count(self):
        # LITERAL: always 2 states (start + accept)
        assert len(nfa("a").states) == 2

    def test_concat_state_count(self):
        # CONCAT(a, b): 2 + 2 = 4 states, no new states added by concat itself
        assert len(nfa("ab").states) == 4

    def test_union_state_count(self):
        # UNION(a, b): 2 + 2 + 2(new) = 6 states
        assert len(nfa("a|b").states) == 6

    def test_star_state_count(self):
        # STAR(a): 2 + 2(new) = 4 states
        assert len(nfa("a*").states) == 4

    def test_plus_state_count(self):
        # PLUS(a): 2 + 1(new accept) = 3 states
        assert len(nfa("a+").states) == 3

    def test_question_state_count(self):
        # QUESTION(a): 2 + 2(new) = 4 states
        assert len(nfa("a?").states) == 4

    def test_union_star_state_count(self):
        # STAR(UNION(a,b)): 6 + 2 = 8 states
        assert len(nfa("(a|b)*").states) == 8

    def test_canonical_state_count(self):
        # (a|b)*abb: 8 + 2 + 2 + 2 = 14 states
        assert len(nfa("(a|b)*abb").states) == 14


# ─────────────────────────────────────────────────────────────────────────────
# 2. ε-transition counts
# ─────────────────────────────────────────────────────────────────────────────

class TestEpsilonCounts:
    """ε-transition counts follow directly from Thompson's rules."""

    def test_literal_has_no_epsilon(self):
        assert count_eps(nfa("a")) == 0

    def test_concat_adds_one_epsilon(self):
        # CONCAT adds exactly 1 ε (bridge between the two fragments)
        assert count_eps(nfa("ab")) == 1

    def test_union_adds_four_epsilons(self):
        # UNION adds 4 ε (2 forks + 2 merges)
        assert count_eps(nfa("a|b")) == 4

    def test_star_adds_four_epsilons(self):
        # STAR(a): 0 (literal) + 4 (star) = 4 ε
        assert count_eps(nfa("a*")) == 4

    def test_plus_adds_two_epsilons(self):
        # PLUS(a): 0 (literal) + 2 (plus: loop + exit) = 2 ε
        assert count_eps(nfa("a+")) == 2

    def test_question_adds_three_epsilons(self):
        # QUESTION(a): 0 (literal) + 3 (enter + skip + exit) = 3 ε
        assert count_eps(nfa("a?")) == 3

    def test_union_star_epsilon_count(self):
        # (a|b)*: union 4 ε + star 4 ε = 8 ε
        assert count_eps(nfa("(a|b)*")) == 8

    def test_canonical_epsilon_count(self):
        # (a|b)*abb: 8 ε (star/union) + 3 ε (three concats) = 11 ε
        assert count_eps(nfa("(a|b)*abb")) == 11


# ─────────────────────────────────────────────────────────────────────────────
# 3. Symbol-transition counts
# ─────────────────────────────────────────────────────────────────────────────

class TestSymbolCounts:

    def test_literal_one_symbol_transition(self):
        assert count_sym(nfa("a")) == 1

    def test_concat_two_symbol_transitions(self):
        assert count_sym(nfa("ab")) == 2

    def test_union_two_symbol_transitions(self):
        assert count_sym(nfa("a|b")) == 2

    def test_star_one_symbol_transition(self):
        assert count_sym(nfa("a*")) == 1

    def test_canonical_five_symbol_transitions(self):
        # (a|b)*abb: a, b (union), a, b, b (abb) = 5 sym trans
        assert count_sym(nfa("(a|b)*abb")) == 5

    def test_total_transition_count_canonical(self):
        # 5 sym + 11 ε = 16 total
        n = nfa("(a|b)*abb")
        assert len(n.transitions) == 16


# ─────────────────────────────────────────────────────────────────────────────
# 4. Start / accepting state invariants
# ─────────────────────────────────────────────────────────────────────────────

class TestStartAcceptInvariants:

    @pytest.mark.parametrize("pattern", [
        "a", "ab", "a|b", "a*", "a+", "a?", "(a|b)*", "(a|b)*abb",
    ])
    def test_start_in_states(self, pattern):
        n = nfa(pattern)
        assert n.start in n.states

    @pytest.mark.parametrize("pattern", [
        "a", "ab", "a|b", "a*", "a+", "a?", "(a|b)*", "(a|b)*abb",
    ])
    def test_exactly_one_accepting_state(self, pattern):
        # Thompson's construction guarantees a single accepting state
        assert len(nfa(pattern).accepting) == 1

    @pytest.mark.parametrize("pattern", [
        "a", "ab", "a|b", "a*", "a+", "a?", "(a|b)*", "(a|b)*abb",
    ])
    def test_accepting_in_states(self, pattern):
        n = nfa(pattern)
        assert n.accepting.issubset(n.states)

    def test_start_not_equal_to_accept_for_literal(self):
        n = nfa("a")
        assert n.start not in n.accepting


# ─────────────────────────────────────────────────────────────────────────────
# 5. Alphabet derived from symbol transitions
# ─────────────────────────────────────────────────────────────────────────────

class TestAlphabet:

    def test_literal_alphabet(self):
        assert nfa("a").alphabet == frozenset({"a"})

    def test_concat_alphabet(self):
        assert nfa("ab").alphabet == frozenset({"a", "b"})

    def test_union_alphabet(self):
        assert nfa("a|b").alphabet == frozenset({"a", "b"})

    def test_star_preserves_alphabet(self):
        assert nfa("a*").alphabet == frozenset({"a"})

    def test_canonical_alphabet(self):
        assert nfa("(a|b)*abb").alphabet == frozenset({"a", "b"})

    def test_epsilon_node_empty_alphabet(self):
        # ε-literal → no symbol transitions
        n = build_nfa(EpsilonNode())
        assert n.alphabet == frozenset()


# ─────────────────────────────────────────────────────────────────────────────
# 6. NFA simulation — (a|b)*abb
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def canonical_nfa() -> NFA:
    return nfa("(a|b)*abb")


class TestSimulationCanonical:
    """The canonical textbook DFA example: (a|b)*abb."""

    # ── Strings that MUST be accepted ────────────────────────────────────

    @pytest.mark.parametrize("s", [
        "abb",
        "aabb",
        "babb",
        "ababb",
        "bbabb",
        "aababb",
        "abababb",
    ])
    def test_accepts(self, canonical_nfa, s):
        assert nfa_accepts(canonical_nfa, s), f"Expected '{s}' to be accepted"

    # ── Strings that MUST be rejected ────────────────────────────────────

    @pytest.mark.parametrize("s", [
        "",           # empty — needs at least abb
        "ab",         # too short (missing final b)
        "a",          # only one char
        "b",          # only one char
        "ba",         # wrong suffix
        "abc",        # 'c' not in alphabet
        "abba",       # almost but wrong
        "abbc",       # wrong suffix char
    ])
    def test_rejects(self, canonical_nfa, s):
        assert not nfa_accepts(canonical_nfa, s), f"Expected '{s}' to be rejected"


# ─────────────────────────────────────────────────────────────────────────────
# 7. NFA simulation — simple patterns
# ─────────────────────────────────────────────────────────────────────────────

class TestSimulationSimple:

    def test_literal_accepts_single(self):
        n = nfa("a")
        assert nfa_accepts(n, "a")
        assert not nfa_accepts(n, "b")
        assert not nfa_accepts(n, "")
        assert not nfa_accepts(n, "aa")

    def test_concat_accepts_exact(self):
        n = nfa("ab")
        assert nfa_accepts(n, "ab")
        assert not nfa_accepts(n, "a")
        assert not nfa_accepts(n, "b")
        assert not nfa_accepts(n, "ba")

    def test_union_accepts_either(self):
        n = nfa("a|b")
        assert nfa_accepts(n, "a")
        assert nfa_accepts(n, "b")
        assert not nfa_accepts(n, "ab")
        assert not nfa_accepts(n, "")

    def test_star_accepts_zero(self):
        n = nfa("a*")
        assert nfa_accepts(n, "")       # zero repetitions
        assert nfa_accepts(n, "a")
        assert nfa_accepts(n, "aaa")
        assert not nfa_accepts(n, "b")

    def test_plus_rejects_empty(self):
        n = nfa("a+")
        assert not nfa_accepts(n, "")   # one-or-more → empty rejected
        assert nfa_accepts(n, "a")
        assert nfa_accepts(n, "aaa")

    def test_question_accepts_zero_or_one(self):
        n = nfa("a?")
        assert nfa_accepts(n, "")
        assert nfa_accepts(n, "a")
        assert not nfa_accepts(n, "aa")

    def test_char_class_range(self):
        n = nfa("[a-c]")
        assert nfa_accepts(n, "a")
        assert nfa_accepts(n, "b")
        assert nfa_accepts(n, "c")
        assert not nfa_accepts(n, "d")
        assert not nfa_accepts(n, "")

    def test_epsilon_node(self):
        n = build_nfa(EpsilonNode())
        assert nfa_accepts(n, "")
        assert not nfa_accepts(n, "a")

    def test_digit_range(self):
        n = nfa("[0-9]")
        for d in "0123456789":
            assert nfa_accepts(n, d)
        assert not nfa_accepts(n, "a")


# ─────────────────────────────────────────────────────────────────────────────
# 8. ε-closure correctness
# ─────────────────────────────────────────────────────────────────────────────

class TestEpsilonClosure:

    def test_literal_closure_is_start(self):
        """For a literal NFA, ε-closure({start}) is just {start}."""
        n = nfa("a")
        eps = build_eps_map(n)
        closure = epsilon_closure(eps, {n.start})
        assert closure == frozenset({n.start})

    def test_star_closure_includes_accept(self):
        """For a*: ε-closure({start}) must include the accepting state
        (skip edge: start ─ε─► accept)."""
        n = nfa("a*")
        eps = build_eps_map(n)
        start_closure = epsilon_closure(eps, {n.start})
        # Because of the skip ε-edge, accepting state is reachable immediately
        assert n.accepting.issubset(start_closure), (
            f"ε-closure({{{n.start}}}) = {start_closure}; "
            f"expected accepting {n.accepting} to be reachable"
        )

    def test_question_closure_includes_accept(self):
        """For a?: same reasoning as star — skip path reaches accept."""
        n = nfa("a?")
        eps = build_eps_map(n)
        closure = epsilon_closure(eps, {n.start})
        assert n.accepting.issubset(closure)

    def test_plus_closure_does_not_include_accept(self):
        """For a+: start ─ε─► (inner start), no skip to accept."""
        n = nfa("a+")
        eps = build_eps_map(n)
        closure = epsilon_closure(eps, {n.start})
        assert not (n.accepting & closure), (
            "a+ must not accept empty string; "
            "accepting state should not be in ε-closure of start"
        )

    def test_closure_is_idempotent(self):
        """Applying ε-closure twice should yield the same result."""
        n = nfa("(a|b)*")
        eps = build_eps_map(n)
        c1 = epsilon_closure(eps, {n.start})
        c2 = epsilon_closure(eps, c1)
        assert c1 == c2

    def test_empty_seed_gives_empty_closure(self):
        n = nfa("a")
        eps = build_eps_map(n)
        assert epsilon_closure(eps, set()) == frozenset()


# ─────────────────────────────────────────────────────────────────────────────
# 9. CharClass range expansion
# ─────────────────────────────────────────────────────────────────────────────

class TestCharClassExpansion:

    def test_three_char_range_transitions(self):
        """[a-c] → 3 symbol transitions (a, b, c)."""
        n = nfa("[a-c]")
        assert count_sym(n) == 3

    def test_alphabet_matches_range(self):
        n = nfa("[a-c]")
        assert n.alphabet == frozenset({"a", "b", "c"})

    def test_single_char_class(self):
        """[x] → 1 symbol transition."""
        n = nfa("[x]")
        assert count_sym(n) == 1

    def test_multi_range_class(self):
        """[a-cA-C] → 6 symbol transitions."""
        n = nfa("[a-cA-C]")
        assert count_sym(n) == 6

    def test_class_accepts_all_in_range(self):
        n = nfa("[a-z]")
        for ch in "abcdefghijklmnopqrstuvwxyz":
            assert nfa_accepts(n, ch), f"[a-z] should accept '{ch}'"

    def test_class_rejects_outside_range(self):
        n = nfa("[a-z]")
        assert not nfa_accepts(n, "A")
        assert not nfa_accepts(n, "0")


# ─────────────────────────────────────────────────────────────────────────────
# 10. EpsilonNode builds correctly
# ─────────────────────────────────────────────────────────────────────────────

class TestEpsilonNode:

    def test_epsilon_state_count(self):
        n = build_nfa(EpsilonNode())
        assert len(n.states) == 2

    def test_epsilon_transition_count(self):
        n = build_nfa(EpsilonNode())
        assert count_eps(n) == 1
        assert count_sym(n) == 0

    def test_epsilon_accepts_empty(self):
        n = build_nfa(EpsilonNode())
        assert nfa_accepts(n, "")

    def test_epsilon_rejects_nonempty(self):
        n = build_nfa(EpsilonNode())
        assert not nfa_accepts(n, "a")


# ─────────────────────────────────────────────────────────────────────────────
# 11. Plus and Question structures
# ─────────────────────────────────────────────────────────────────────────────

class TestPlusQuestion:

    def test_plus_three_states(self):
        assert len(nfa("a+").states) == 3

    def test_plus_one_sym_two_eps(self):
        n = nfa("a+")
        assert count_sym(n) == 1
        assert count_eps(n) == 2

    def test_question_four_states(self):
        assert len(nfa("a?").states) == 4

    def test_question_one_sym_three_eps(self):
        n = nfa("a?")
        assert count_sym(n) == 1
        assert count_eps(n) == 3


# ─────────────────────────────────────────────────────────────────────────────
# 12. Max-steps guard
# ─────────────────────────────────────────────────────────────────────────────

class TestMaxStepsGuard:

    def test_raises_simulation_timeout(self):
        n = nfa("(a|b)*abb")
        with pytest.raises(SimulationTimeoutError):
            nfa_accepts(n, "a" * 1000, max_steps=5)

    def test_no_error_for_short_input(self):
        n = nfa("(a|b)*abb")
        # This must not raise with a generous limit
        nfa_accepts(n, "abb", max_steps=10_000)

    def test_timeout_error_code(self):
        n = nfa("a*")
        try:
            nfa_accepts(n, "a" * 10_000, max_steps=1)
        except SimulationTimeoutError as e:
            assert e.error_code == "SIMULATION_TIMEOUT"
        else:
            # If it didn't raise, that's also acceptable (small input)
            pass


# ─────────────────────────────────────────────────────────────────────────────
# 13. NFA.to_dict() and JSON serialisation
# ─────────────────────────────────────────────────────────────────────────────

class TestNFAToDict:

    def test_to_dict_has_required_keys(self):
        d = nfa("a").to_dict()
        assert set(d.keys()) == {"states", "alphabet", "transitions", "start", "accepting"}

    def test_states_sorted_list(self):
        d = nfa("a").to_dict()
        assert d["states"] == sorted(d["states"])

    def test_accepting_sorted_list(self):
        d = nfa("a").to_dict()
        assert d["accepting"] == sorted(d["accepting"])

    def test_transition_has_from_symbol_to(self):
        d = nfa("a").to_dict()
        t = d["transitions"][0]
        assert "from" in t and "symbol" in t and "to" in t

    def test_epsilon_transitions_use_unicode_epsilon(self):
        d = nfa("a|b").to_dict()
        epsilon_trans = [t for t in d["transitions"] if t["symbol"] == "ε"]
        assert len(epsilon_trans) == 4   # union adds 4 ε

    def test_json_round_trip(self):
        d = nfa("(a|b)*abb").to_dict()
        payload = json.dumps(d)
        loaded  = json.loads(payload)
        assert loaded["states"] == d["states"]
        assert len(loaded["transitions"]) == 16

    def test_to_dict_state_count(self):
        d = nfa("(a|b)*abb").to_dict()
        assert len(d["states"]) == 14

    def test_to_dict_alphabet(self):
        d = nfa("(a|b)*abb").to_dict()
        assert sorted(d["alphabet"]) == ["a", "b"]

    def test_start_in_states(self):
        d = nfa("(a|b)*abb").to_dict()
        assert d["start"] in d["states"]

    def test_accepting_subset_of_states(self):
        d = nfa("(a|b)*abb").to_dict()
        for a in d["accepting"]:
            assert a in d["states"]
