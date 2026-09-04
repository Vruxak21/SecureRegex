"""
Phase 5 — Subset Construction (NFA → DFA) tests.

DFA state / transition counts for (a|b)*abb
--------------------------------------------
The classic Dragon Book result.  Manual trace:

  NFA start closure D0 = ε-closure({6}) = {0,2,4,6,7,8}

  Symbol 'a':
    D0 ──a──► {1,9} → ε-closure = {0,1,2,4,5,7,8,9,10}  ≡ D1
  Symbol 'b':
    D0 ──b──► {3}   → ε-closure = {0,2,3,4,5,7,8}        ≡ D2

  D1 ──a──► {1,9}  → D1  (self-loop)
  D1 ──b──► {3,11} → ε-closure = {0,2,3,4,5,7,8,11,12}  ≡ D3

  D2 ──a──► {1,9}  → D1
  D2 ──b──► {3}    → D2  (self-loop)

  D3 ──a──► {1,9}  → D1
  D3 ──b──► {3,13} → ε-closure = {0,2,3,4,5,7,8,13}      ≡ D4  ← ACCEPTING

  D4 ──a──► {1,9}  → D1
  D4 ──b──► {3}    → D2

  Result:
    DFA states    : 5   (D0–D4, IDs 0–4)
    DFA transitions: 10  (2 per state × 5 states, complete)
    Accepting      : {D4}

Coverage targets
----------------
1.  Determinism: at most one transition per (state, symbol) pair
2.  State count for (a|b)*abb == 5
3.  Transition count for (a|b)*abb == 10
4.  Accepting state count == 1
5.  Start state always ID 0
6.  DFA and NFA agree on all test strings (property test)
7.  dfa_accepts: correct accept / reject for canonical pattern
8.  dfa_accepts: simple patterns (literal, concat, union, star, plus, question)
9.  build_trans_map returns correct lookup structure
10. DFA.to_dict() structure and JSON round-trip
11. DFAConstructionError raised when max_states exceeded
12. DFAConstructionError has correct error_code
13. Alphabet preserved from NFA
14. CharClass DFA accepts correct characters
15. is_complete() True for complete DFA
"""

from __future__ import annotations

import json

import pytest

from app.dfa        import DFA, DFATransition, build_dfa, build_trans_map, dfa_accepts
from app.exceptions import DFAConstructionError
from app.nfa        import NFA, build_nfa, nfa_accepts
from app.parser     import parse_pattern


# ── Helpers ───────────────────────────────────────────────────────────────────

def pipeline(pattern: str) -> tuple[NFA, DFA]:
    """Parse → NFA → DFA in one call."""
    nfa = build_nfa(parse_pattern(pattern))
    dfa = build_dfa(nfa)
    return nfa, dfa


def dfa_only(pattern: str) -> DFA:
    return pipeline(pattern)[1]


# Accept / reject strings for the canonical pattern
_CANONICAL_ACCEPT = ["abb", "aabb", "babb", "ababb", "bbabb", "abababb"]
_CANONICAL_REJECT = ["", "ab", "a", "b", "ba", "abc", "abba"]


# ─────────────────────────────────────────────────────────────────────────────
# 1. Determinism — at most one transition per (state, symbol)
# ─────────────────────────────────────────────────────────────────────────────

class TestDeterminism:
    """A valid DFA must have ≤ 1 outgoing edge per (state, symbol) pair."""

    @pytest.mark.parametrize("pattern", [
        "a", "ab", "a|b", "a*", "a+", "a?", "(a|b)*", "(a|b)*abb",
        "[a-z]+", "[0-9]*",
    ])
    def test_at_most_one_transition_per_state_symbol(self, pattern):
        dfa = dfa_only(pattern)
        seen: set[tuple[int, str]] = set()
        for t in dfa.transitions:
            key = (t.from_id, t.symbol)
            assert key not in seen, (
                f"Non-deterministic DFA: state {t.from_id} has two "
                f"transitions on '{t.symbol}'"
            )
            seen.add(key)

    def test_canonical_is_deterministic(self):
        dfa = dfa_only("(a|b)*abb")
        pairs = [(t.from_id, t.symbol) for t in dfa.transitions]
        assert len(pairs) == len(set(pairs))


# ─────────────────────────────────────────────────────────────────────────────
# 2 & 3. State / transition counts for (a|b)*abb
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def canonical_dfa_fixture() -> DFA:
    return dfa_only("(a|b)*abb")


class TestCanonicalCounts:

    def test_state_count(self, canonical_dfa_fixture):
        assert len(canonical_dfa_fixture.states) == 5

    def test_transition_count(self, canonical_dfa_fixture):
        assert len(canonical_dfa_fixture.transitions) == 10

    def test_accepting_count(self, canonical_dfa_fixture):
        assert len(canonical_dfa_fixture.accepting) == 1

    def test_start_is_zero(self, canonical_dfa_fixture):
        assert canonical_dfa_fixture.start == 0

    def test_start_in_states(self, canonical_dfa_fixture):
        assert 0 in canonical_dfa_fixture.states

    def test_accepting_in_states(self, canonical_dfa_fixture):
        assert canonical_dfa_fixture.accepting.issubset(canonical_dfa_fixture.states)

    def test_is_complete(self, canonical_dfa_fixture):
        assert canonical_dfa_fixture.is_complete()

    def test_alphabet_is_a_b(self, canonical_dfa_fixture):
        assert canonical_dfa_fixture.alphabet == frozenset({"a", "b"})


# ─────────────────────────────────────────────────────────────────────────────
# 4 & 5. Start state always 0
# ─────────────────────────────────────────────────────────────────────────────

class TestStartState:

    @pytest.mark.parametrize("pattern", [
        "a", "ab", "a|b", "a*", "(a|b)*abb",
    ])
    def test_start_always_zero(self, pattern):
        assert dfa_only(pattern).start == 0


# ─────────────────────────────────────────────────────────────────────────────
# 6. DFA ↔ NFA agreement (property test)
# ─────────────────────────────────────────────────────────────────────────────

class TestDFANFAEquivalence:
    """DFA and NFA must give the same accept/reject on every test string."""

    _STRINGS = [
        "", "a", "b", "c",
        "ab", "ba", "aa", "bb",
        "abb", "aabb", "babb", "aba",
        "abba", "abbc", "abab",
        "0", "9", "az",
    ]

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
    ])
    def test_dfa_nfa_agree(self, pattern):
        nfa, dfa = pipeline(pattern)
        for s in self._STRINGS:
            nfa_result = nfa_accepts(nfa, s)
            dfa_result = dfa_accepts(dfa, s)
            assert nfa_result == dfa_result, (
                f"Pattern {pattern!r}: disagreement on {s!r} — "
                f"NFA={nfa_result}, DFA={dfa_result}"
            )


# ─────────────────────────────────────────────────────────────────────────────
# 7. dfa_accepts — canonical pattern
# ─────────────────────────────────────────────────────────────────────────────

class TestDFAAcceptsCanonical:

    @pytest.fixture
    def canonical_dfa(self) -> DFA:
        return dfa_only("(a|b)*abb")

    @pytest.mark.parametrize("s", _CANONICAL_ACCEPT)
    def test_accepts(self, canonical_dfa, s):
        assert dfa_accepts(canonical_dfa, s), f"Expected '{s}' to be accepted"

    @pytest.mark.parametrize("s", _CANONICAL_REJECT)
    def test_rejects(self, canonical_dfa, s):
        assert not dfa_accepts(canonical_dfa, s), f"Expected '{s}' to be rejected"


# ─────────────────────────────────────────────────────────────────────────────
# 8. dfa_accepts — simple patterns
# ─────────────────────────────────────────────────────────────────────────────

class TestDFAAcceptsSimple:

    def test_literal(self):
        dfa = dfa_only("a")
        assert dfa_accepts(dfa, "a")
        assert not dfa_accepts(dfa, "b")
        assert not dfa_accepts(dfa, "")
        assert not dfa_accepts(dfa, "aa")

    def test_concat(self):
        dfa = dfa_only("ab")
        assert dfa_accepts(dfa, "ab")
        assert not dfa_accepts(dfa, "a")
        assert not dfa_accepts(dfa, "b")
        assert not dfa_accepts(dfa, "ba")

    def test_union(self):
        dfa = dfa_only("a|b")
        assert dfa_accepts(dfa, "a")
        assert dfa_accepts(dfa, "b")
        assert not dfa_accepts(dfa, "ab")
        assert not dfa_accepts(dfa, "")

    def test_star_accepts_empty(self):
        dfa = dfa_only("a*")
        assert dfa_accepts(dfa, "")
        assert dfa_accepts(dfa, "a")
        assert dfa_accepts(dfa, "aaa")
        assert not dfa_accepts(dfa, "b")

    def test_plus_rejects_empty(self):
        dfa = dfa_only("a+")
        assert not dfa_accepts(dfa, "")
        assert dfa_accepts(dfa, "a")
        assert dfa_accepts(dfa, "aaaa")

    def test_question(self):
        dfa = dfa_only("a?")
        assert dfa_accepts(dfa, "")
        assert dfa_accepts(dfa, "a")
        assert not dfa_accepts(dfa, "aa")

    def test_char_class(self):
        dfa = dfa_only("[a-c]")
        assert dfa_accepts(dfa, "a")
        assert dfa_accepts(dfa, "b")
        assert dfa_accepts(dfa, "c")
        assert not dfa_accepts(dfa, "d")
        assert not dfa_accepts(dfa, "")

    def test_digit_class_plus(self):
        dfa = dfa_only("[0-9]+")
        assert dfa_accepts(dfa, "0")
        assert dfa_accepts(dfa, "42")
        assert not dfa_accepts(dfa, "")
        assert not dfa_accepts(dfa, "a")


# ─────────────────────────────────────────────────────────────────────────────
# 9. build_trans_map
# ─────────────────────────────────────────────────────────────────────────────

class TestBuildTransMap:

    def test_returns_dict_keyed_by_state(self):
        dfa = dfa_only("a|b")
        tm  = build_trans_map(dfa)
        for s in dfa.states:
            assert s in tm

    def test_each_value_is_symbol_to_state(self):
        dfa = dfa_only("ab")
        tm  = build_trans_map(dfa)
        for state, sym_map in tm.items():
            for sym, dest in sym_map.items():
                assert isinstance(sym, str)
                assert dest in dfa.states

    def test_trans_map_gives_same_accepts_as_default(self):
        dfa = dfa_only("(a|b)*abb")
        tm  = build_trans_map(dfa)
        for s in _CANONICAL_ACCEPT:
            assert dfa_accepts(dfa, s, trans_map=tm)
        for s in _CANONICAL_REJECT:
            assert not dfa_accepts(dfa, s, trans_map=tm)

    def test_precomputed_map_equals_fresh(self):
        dfa = dfa_only("(a|b)*abb")
        tm1 = build_trans_map(dfa)
        tm2 = build_trans_map(dfa)
        assert tm1 == tm2


# ─────────────────────────────────────────────────────────────────────────────
# 10. DFA.to_dict() and JSON serialisation
# ─────────────────────────────────────────────────────────────────────────────

class TestDFAToDict:

    def test_has_required_keys(self):
        d = dfa_only("a").to_dict()
        assert set(d.keys()) == {"states", "alphabet", "transitions", "start", "accepting"}

    def test_states_is_sorted_list(self):
        d = dfa_only("a|b").to_dict()
        assert d["states"] == sorted(d["states"])

    def test_accepting_is_sorted_list(self):
        d = dfa_only("(a|b)*abb").to_dict()
        assert d["accepting"] == sorted(d["accepting"])

    def test_transition_keys(self):
        d = dfa_only("a").to_dict()
        for t in d["transitions"]:
            assert "from" in t
            assert "symbol" in t
            assert "to" in t

    def test_no_epsilon_in_transitions(self):
        """DFA transitions must never carry 'ε'."""
        d = dfa_only("(a|b)*abb").to_dict()
        for t in d["transitions"]:
            assert t["symbol"] != "ε", "DFA transitions must not be ε"

    def test_json_round_trip(self):
        d = dfa_only("(a|b)*abb").to_dict()
        loaded = json.loads(json.dumps(d))
        assert loaded["states"]  == d["states"]
        assert len(loaded["transitions"]) == 10
        assert loaded["start"]   == 0

    def test_canonical_state_count_in_dict(self):
        assert len(dfa_only("(a|b)*abb").to_dict()["states"]) == 5

    def test_start_always_zero_in_dict(self):
        assert dfa_only("(a|b)*abb").to_dict()["start"] == 0


# ─────────────────────────────────────────────────────────────────────────────
# 11 & 12. Blowup guard — DFAConstructionError
# ─────────────────────────────────────────────────────────────────────────────

class TestBlowupGuard:

    def test_raises_dfa_construction_error(self):
        """Setting max_states=2 on (a|b)*abb (which needs 5) must raise."""
        nfa = build_nfa(parse_pattern("(a|b)*abb"))
        with pytest.raises(DFAConstructionError):
            build_dfa(nfa, max_states=2)

    def test_error_code(self):
        nfa = build_nfa(parse_pattern("(a|b)*abb"))
        try:
            build_dfa(nfa, max_states=2)
        except DFAConstructionError as e:
            assert e.error_code == "DFA_CONSTRUCTION_ERROR"
        else:
            pytest.fail("Expected DFAConstructionError")

    def test_error_message_mentions_limit(self):
        nfa = build_nfa(parse_pattern("(a|b)*abb"))
        try:
            build_dfa(nfa, max_states=2)
        except DFAConstructionError as e:
            assert "2" in e.message or "limit" in e.message.lower()

    def test_no_error_when_limit_generous(self):
        nfa = build_nfa(parse_pattern("(a|b)*abb"))
        dfa = build_dfa(nfa, max_states=1000)
        assert len(dfa.states) == 5

    def test_limit_of_exactly_five_succeeds(self):
        """max_states=5 must succeed for (a|b)*abb (needs exactly 5)."""
        nfa = build_nfa(parse_pattern("(a|b)*abb"))
        dfa = build_dfa(nfa, max_states=5)
        assert len(dfa.states) == 5

    def test_limit_of_four_fails(self):
        """max_states=4 must fail for (a|b)*abb (needs 5)."""
        nfa = build_nfa(parse_pattern("(a|b)*abb"))
        with pytest.raises(DFAConstructionError):
            build_dfa(nfa, max_states=4)

    def test_complex_pattern_blowup(self):
        """A char-class pattern with many symbols needs more than 1 DFA state."""
        nfa = build_nfa(parse_pattern("[a-z]+"))
        with pytest.raises(DFAConstructionError):
            build_dfa(nfa, max_states=1)


# ─────────────────────────────────────────────────────────────────────────────
# 13. Alphabet
# ─────────────────────────────────────────────────────────────────────────────

class TestAlphabet:

    def test_literal_alphabet(self):
        assert dfa_only("a").alphabet == frozenset({"a"})

    def test_concat_alphabet(self):
        assert dfa_only("ab").alphabet == frozenset({"a", "b"})

    def test_canonical_alphabet(self):
        assert dfa_only("(a|b)*abb").alphabet == frozenset({"a", "b"})

    def test_char_class_alphabet(self):
        dfa = dfa_only("[a-c]")
        assert dfa.alphabet == frozenset({"a", "b", "c"})

    def test_no_symbols_outside_alphabet(self):
        dfa = dfa_only("(a|b)*abb")
        for t in dfa.transitions:
            assert t.symbol in dfa.alphabet


# ─────────────────────────────────────────────────────────────────────────────
# 14. CharClass DFA
# ─────────────────────────────────────────────────────────────────────────────

class TestCharClassDFA:

    def test_single_range_accepted(self):
        dfa = dfa_only("[a-z]")
        for c in "abcdefghijklmnopqrstuvwxyz":
            assert dfa_accepts(dfa, c)

    def test_digit_range_rejected_for_alpha(self):
        dfa = dfa_only("[0-9]")
        assert not dfa_accepts(dfa, "a")

    def test_nfa_dfa_agree_on_class(self):
        nfa, dfa = pipeline("[a-c]+")
        for s in ["", "a", "b", "c", "abc", "d", "aa", "dc"]:
            assert nfa_accepts(nfa, s) == dfa_accepts(dfa, s)


# ─────────────────────────────────────────────────────────────────────────────
# 15. is_complete()
# ─────────────────────────────────────────────────────────────────────────────

class TestIsComplete:

    def test_canonical_is_complete(self):
        # (a|b)*abb generates a complete DFA (all states have transitions on a and b)
        assert dfa_only("(a|b)*abb").is_complete()

    def test_literal_is_not_complete(self):
        # "a": start state has transition on 'a', but accept state has none → incomplete
        dfa = dfa_only("a")
        assert not dfa.is_complete()

    def test_char_class_star_complete(self):
        # "[ab]*" — both states should have transitions on both symbols
        assert dfa_only("[ab]*").is_complete()
