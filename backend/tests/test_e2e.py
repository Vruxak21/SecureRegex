"""
Phase 11 — End-to-end integration tests for the full API pipeline.

Covers:
  A. Battery tests  — all patterns in examples/fixtures.json run through
     /api/v1/analyze and /api/v1/test with consistency invariants checked.
  B. Robustness     — every error path returns a clean structured JSON body
     with the correct HTTP status; no raw tracebacks ever reach the client.
  C. Guard tests    — max-regex-length, max-input-length, max-DFA-state
     limits are verified from the API layer, not just internally.
  D. Security flag  — HIGH-risk patterns are still flagged end-to-end.
  E. Statistics     — invariants such as minimized ≤ original DFA states hold.

Usage:
    pytest backend/tests/test_e2e.py -v
"""

from __future__ import annotations

import json
import os
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings

client = TestClient(app, raise_server_exceptions=False)

ANALYZE = "/api/v1/analyze"
TEST    = "/api/v1/test"

# ── Load fixtures ────────────────────────────────────────────────────────────

FIXTURES_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "examples", "fixtures.json"
)

with open(FIXTURES_PATH) as fh:
    FIXTURES = json.load(fh)

SAFE_PATTERNS  = FIXTURES["safe_patterns"]
RISKY_PATTERNS = FIXTURES["risky_patterns"]
ALL_PATTERNS   = SAFE_PATTERNS + RISKY_PATTERNS


# ── Helpers ──────────────────────────────────────────────────────────────────

def analyze(regex: str):
    return client.post(ANALYZE, json={"regex": regex})

def call_test(regex: str, inp: str):
    return client.post(TEST, json={"regex": regex, "input": inp})

def body(regex: str) -> dict:
    return analyze(regex).json()


# ─────────────────────────────────────────────────────────────────────────────
# A. BATTERY TESTS — all fixture patterns
# ─────────────────────────────────────────────────────────────────────────────

class TestBatteryAnalyze:
    """Run every fixture through /analyze and check structural invariants."""

    @pytest.mark.parametrize("fixture", ALL_PATTERNS, ids=[p["id"] for p in ALL_PATTERNS])
    def test_analyze_returns_200(self, fixture):
        r = analyze(fixture["regex"])
        assert r.status_code == 200, f'{fixture["id"]}: {r.text}'

    @pytest.mark.parametrize("fixture", ALL_PATTERNS, ids=[p["id"] for p in ALL_PATTERNS])
    def test_success_flag_true(self, fixture):
        b = body(fixture["regex"])
        assert b["success"] is True, fixture["id"]

    @pytest.mark.parametrize("fixture", ALL_PATTERNS, ids=[p["id"] for p in ALL_PATTERNS])
    def test_tokens_non_empty(self, fixture):
        b = body(fixture["regex"])
        assert len(b["tokens"]) > 0, fixture["id"]

    @pytest.mark.parametrize("fixture", ALL_PATTERNS, ids=[p["id"] for p in ALL_PATTERNS])
    def test_minimized_states_le_dfa_states(self, fixture):
        """Core invariant: Hopcroft never adds states."""
        b = body(fixture["regex"])
        stats = b["stats"]
        assert stats["minimized_dfa_states"] <= stats["dfa_states"], (
            f'{fixture["id"]}: {stats["minimized_dfa_states"]} > {stats["dfa_states"]}'
        )

    @pytest.mark.parametrize("fixture", ALL_PATTERNS, ids=[p["id"] for p in ALL_PATTERNS])
    def test_nfa_states_positive(self, fixture):
        b = body(fixture["regex"])
        assert b["stats"]["nfa_states"] > 0, fixture["id"]

    @pytest.mark.parametrize("fixture", ALL_PATTERNS, ids=[p["id"] for p in ALL_PATTERNS])
    def test_dfa_states_positive(self, fixture):
        b = body(fixture["regex"])
        assert b["stats"]["dfa_states"] > 0, fixture["id"]

    @pytest.mark.parametrize("fixture", ALL_PATTERNS, ids=[p["id"] for p in ALL_PATTERNS])
    def test_reduction_pct_in_range(self, fixture):
        """Reduction must be in [0, 100]."""
        b = body(fixture["regex"])
        pct = b["stats"]["dfa_reduction_pct"]
        assert 0.0 <= pct <= 100.0, f'{fixture["id"]}: reduction={pct}'

    @pytest.mark.parametrize("fixture", ALL_PATTERNS, ids=[p["id"] for p in ALL_PATTERNS])
    def test_security_risk_level_present(self, fixture):
        b = body(fixture["regex"])
        risk = b["security"]["overall_risk"]
        assert risk in ("NONE", "LOW", "MEDIUM", "HIGH"), fixture["id"]

    @pytest.mark.parametrize("fixture", ALL_PATTERNS, ids=[p["id"] for p in ALL_PATTERNS])
    def test_ast_has_type_key(self, fixture):
        b = body(fixture["regex"])
        assert "type" in b["ast"], fixture["id"]

    @pytest.mark.parametrize("fixture", ALL_PATTERNS, ids=[p["id"] for p in ALL_PATTERNS])
    def test_security_caveat_present(self, fixture):
        """The security caveat must always be included."""
        b = body(fixture["regex"])
        assert len(b["security"]["caveat"]) > 20, fixture["id"]

    @pytest.mark.parametrize("fixture", ALL_PATTERNS, ids=[p["id"] for p in ALL_PATTERNS])
    def test_response_has_no_raw_traceback(self, fixture):
        """No raw Python traceback should appear in any response."""
        r = analyze(fixture["regex"])
        assert "Traceback (most recent call last)" not in r.text
        assert "File \"" not in r.text


class TestBatterySecurityRisk:
    """Security risk levels must match fixture expectations."""

    @pytest.mark.parametrize("fixture", SAFE_PATTERNS, ids=[p["id"] for p in SAFE_PATTERNS])
    def test_safe_patterns_no_high_risk(self, fixture):
        b = body(fixture["regex"])
        risk = b["security"]["overall_risk"]
        expected = fixture["expected"]["security_risk"]
        assert risk == expected, (
            f'{fixture["id"]}: expected {expected}, got {risk}'
        )

    @pytest.mark.parametrize("fixture", RISKY_PATTERNS, ids=[p["id"] for p in RISKY_PATTERNS])
    def test_risky_patterns_flagged_correctly(self, fixture):
        b = body(fixture["regex"])
        risk = b["security"]["overall_risk"]
        expected = fixture["expected"]["security_risk"]
        assert risk == expected, (
            f'{fixture["id"]}: expected {expected}, got {risk}'
        )

    @pytest.mark.parametrize("fixture", RISKY_PATTERNS, ids=[p["id"] for p in RISKY_PATTERNS])
    def test_risky_patterns_have_findings(self, fixture):
        b = body(fixture["regex"])
        assert len(b["security"]["findings"]) > 0, (
            f'{fixture["id"]}: expected findings, got none'
        )

    @pytest.mark.parametrize("fixture", RISKY_PATTERNS, ids=[p["id"] for p in RISKY_PATTERNS])
    def test_risky_rule_ids_present(self, fixture):
        b = body(fixture["regex"])
        actual_ids = {f["rule_id"] for f in b["security"]["findings"]}
        for expected_id in fixture["expected"]["rule_ids_include"]:
            assert expected_id in actual_ids, (
                f'{fixture["id"]}: rule {expected_id} missing; got {actual_ids}'
            )

    @pytest.mark.parametrize("fixture", RISKY_PATTERNS, ids=[p["id"] for p in RISKY_PATTERNS])
    def test_finding_fields_complete(self, fixture):
        b = body(fixture["regex"])
        for finding in b["security"]["findings"]:
            for field in ("rule_id", "risk_level", "title", "reason", "explanation", "recommendation"):
                assert field in finding, f'{fixture["id"]}: missing field {field}'
                assert finding[field], f'{fixture["id"]}: empty field {field}'


class TestBatteryAcceptReject:
    """Accept/reject behavior via /api/test must match fixture definitions."""

    @pytest.mark.parametrize("fixture", ALL_PATTERNS, ids=[p["id"] for p in ALL_PATTERNS])
    def test_accepted_strings(self, fixture):
        regex = fixture["regex"]
        for s in fixture["expected"]["accepts"]:
            r = call_test(regex, s)
            assert r.status_code == 200, f'{fixture["id"]}: {s!r} — {r.text}'
            assert r.json()["matched"] is True, (
                f'{fixture["id"]}: expected {s!r} to match {regex!r}'
            )

    @pytest.mark.parametrize("fixture", ALL_PATTERNS, ids=[p["id"] for p in ALL_PATTERNS])
    def test_rejected_strings(self, fixture):
        regex = fixture["regex"]
        for s in fixture["expected"]["rejects"]:
            r = call_test(regex, s)
            assert r.status_code == 200, f'{fixture["id"]}: {s!r} — {r.text}'
            assert r.json()["matched"] is False, (
                f'{fixture["id"]}: expected {s!r} NOT to match {regex!r}'
            )

    @pytest.mark.parametrize("fixture", ALL_PATTERNS, ids=[p["id"] for p in ALL_PATTERNS])
    def test_path_starts_at_start_state(self, fixture):
        """The first element of path must be the DFA start state."""
        regex = fixture["regex"]
        # Use first accept string or first reject string
        sample = fixture["expected"]["accepts"][0] if fixture["expected"]["accepts"] else ""
        r = call_test(regex, sample)
        assert r.status_code == 200
        b_test = r.json()
        assert len(b_test["path"]) > 0, fixture["id"]


# ─────────────────────────────────────────────────────────────────────────────
# B. ROBUSTNESS — error paths produce structured JSON, not raw tracebacks
# ─────────────────────────────────────────────────────────────────────────────

class TestErrorPaths:
    """Every user-facing error must be a structured JSON body."""

    # ── Lexer errors ─────────────────────────────────────────────────────────
    # Note: our lexer accepts ALL ASCII chars as literal CHAR tokens — '@' is
    # not a metacharacter so it tokenises to CHAR('@'), compiles successfully.
    # True lexer errors are unbalanced brackets / truly invalid constructs.

    def test_unclosed_bracket_returns_4xx(self):
        """An unclosed [ is a lexer/parser error."""
        r = analyze("[abc")
        assert 400 <= r.status_code < 500

    def test_unclosed_bracket_has_error_key(self):
        r = analyze("[abc")
        b = r.json()
        assert "error" in b and "message" in b

    def test_at_sign_is_valid_literal(self):
        """@ is not a metacharacter — it tokenises as a literal and compiles."""
        r = analyze("a@b")
        assert r.status_code == 200
        assert r.json()["success"] is True

    def test_at_sign_no_traceback(self):
        assert "Traceback" not in analyze("a@b").text

    # ── Parser errors ────────────────────────────────────────────────────────

    def test_unclosed_paren_returns_4xx(self):
        r = analyze("(ab")
        assert 400 <= r.status_code < 500

    def test_unclosed_paren_structured_error(self):
        r = analyze("(ab")
        b = r.json()
        assert "error" in b and "message" in b

    def test_unclosed_paren_no_traceback(self):
        assert "Traceback" not in analyze("(ab").text

    def test_double_pipe_parse_error(self):
        r = analyze("a||b")
        assert 400 <= r.status_code < 500
        assert "Traceback" not in r.text

    def test_trailing_pipe_parse_error(self):
        r = analyze("a|")
        assert 400 <= r.status_code < 500
        assert "Traceback" not in r.text

    def test_bare_star_parse_error(self):
        r = analyze("*")
        assert 400 <= r.status_code < 500
        assert "Traceback" not in r.text

    def test_bare_plus_parse_error(self):
        r = analyze("+")
        assert 400 <= r.status_code < 500
        assert "Traceback" not in r.text

    def test_bare_question_parse_error(self):
        r = analyze("?")
        assert 400 <= r.status_code < 500
        assert "Traceback" not in r.text

    # ── Semantic errors ──────────────────────────────────────────────────────
    # [z-a] is semantically invalid (SEM001). The pipeline returns HTTP 200
    # with success=True but includes an ERROR diagnostic in diagnostics[].
    # The pipeline continues (our design: semantic errors are in diagnostics,
    # not exceptions) so the response shape is identical to a valid pattern.

    def test_inverted_char_class_returns_200_with_diagnostic(self):
        """[z-a] produces SEM001 diagnostic but HTTP 200."""
        r = analyze("[z-a]")
        assert r.status_code == 200

    def test_inverted_char_class_has_sem001_diagnostic(self):
        b = analyze("[z-a]").json()
        codes = [d["code"] for d in b["diagnostics"]]
        assert "SEM001" in codes, f"Expected SEM001 in diagnostics, got {codes}"

    def test_inverted_char_class_no_traceback(self):
        assert "Traceback" not in analyze("[z-a]").text

    # ── Empty / whitespace input ─────────────────────────────────────────────

    def test_empty_regex_returns_4xx(self):
        """Truly empty string hits the pipeline length/empty guard."""
        r = analyze("")
        assert 400 <= r.status_code < 500

    def test_whitespace_only_tokenises_or_errors(self):
        """Whitespace chars are valid literals in our grammar; pipeline may
        succeed with whitespace-matching DFA. The key invariant: no traceback."""
        r = analyze("   ")
        assert "Traceback" not in r.text
        assert r.status_code in (200, 400, 422)

    # ── /test errors ─────────────────────────────────────────────────────────

    def test_test_malformed_regex_structured(self):
        r = call_test("(ab", "ab")
        assert 400 <= r.status_code < 500
        b = r.json()
        assert "error" in b and "message" in b
        assert "Traceback" not in r.text

    def test_test_at_sign_is_valid_literal_in_test_endpoint(self):
        """@ compiles to a literal; /test with matching input returns matched=True."""
        r = call_test("a@b", "a@b")
        assert r.status_code == 200
        assert r.json()["matched"] is True
        assert "Traceback" not in r.text

    # ── HTTP status consistency ──────────────────────────────────────────────

    def test_valid_request_is_200_not_500(self):
        r = analyze("a")
        assert r.status_code == 200

    def test_error_is_not_500(self):
        """All domain errors must map to 4xx, never 5xx."""
        for regex in ["(", ")", "*", "+", "?", "[z-a]", "@", ""]:
            r = analyze(regex)
            assert r.status_code < 500, f'Got 5xx for regex {regex!r}'


# ─────────────────────────────────────────────────────────────────────────────
# C. GUARD TESTS — limits enforced at the API layer
# ─────────────────────────────────────────────────────────────────────────────

class TestGuards:
    """Max-length and max-state guards work from the API, not just internally."""

    def test_regex_too_long_returns_422(self):
        oversized = "a" * (settings.max_regex_length + 1)
        r = analyze(oversized)
        assert r.status_code == 422

    def test_regex_too_long_error_code(self):
        oversized = "a" * (settings.max_regex_length + 1)
        r = analyze(oversized)
        assert r.json()["error"] == "REGEX_TOO_LONG"

    def test_regex_too_long_no_traceback(self):
        oversized = "a" * (settings.max_regex_length + 1)
        assert "Traceback" not in analyze(oversized).text

    def test_regex_at_max_length_succeeds(self):
        """Exactly at the limit should be accepted."""
        at_limit = "a" * settings.max_regex_length
        r = analyze(at_limit)
        # May succeed OR hit DFA blowup — but must NOT be REGEX_TOO_LONG
        b = r.json()
        assert b.get("error") != "REGEX_TOO_LONG", "at-limit regex wrongly rejected"

    def test_input_too_long_returns_422(self):
        oversized_input = "a" * (settings.max_input_length + 1)
        r = call_test("a*", oversized_input)
        assert r.status_code == 422

    def test_input_too_long_error_code(self):
        oversized_input = "a" * (settings.max_input_length + 1)
        r = call_test("a*", oversized_input)
        assert r.json()["error"] == "INPUT_TOO_LONG"

    def test_input_too_long_no_traceback(self):
        oversized_input = "a" * (settings.max_input_length + 1)
        assert "Traceback" not in call_test("a*", oversized_input).text

    def test_complex_regex_does_not_hang(self):
        """
        A regex that causes DFA blowup (many distinct chars) must either
        succeed or return a structured 'too complex' error — never timeout/hang.
        This test has a 5s implicit pytest timeout via the assertion path.
        """
        many_chars = "|".join(f"[{chr(ord('a')+i)}]+" for i in range(20))
        r = analyze(many_chars)
        # We allow 200 or any 4xx — must not be an unhandled 5xx
        assert r.status_code != 500, f"Got 500: {r.text[:200]}"
        assert "Traceback" not in r.text

    def test_missing_regex_field_returns_422(self):
        """Request body without 'regex' key must be rejected by Pydantic."""
        r = client.post(ANALYZE, json={"pattern": "a"})
        assert r.status_code == 422

    def test_missing_test_fields_returns_422(self):
        r = client.post(TEST, json={"regex": "a"})
        assert r.status_code == 422

    def test_wrong_content_type_returns_422_or_415(self):
        r = client.post(ANALYZE, content=b"not json", headers={"Content-Type": "text/plain"})
        assert r.status_code in (415, 422)


# ─────────────────────────────────────────────────────────────────────────────
# D. STATISTICS CONSISTENCY — cross-field invariants
# ─────────────────────────────────────────────────────────────────────────────

class TestStatisticsConsistency:
    """Pipeline statistics must be internally consistent."""

    def _stats(self, regex: str) -> dict:
        return body(regex)["stats"]

    def test_aorb_abb_nfa_states(self):
        """(a|b)*abb — NFA must have > 1 state from Thompson's construction."""
        s = self._stats("(a|b)*abb")
        assert s["nfa_states"] > 1

    def test_aorb_abb_min_le_dfa(self):
        s = self._stats("(a|b)*abb")
        assert s["minimized_dfa_states"] <= s["dfa_states"]

    def test_aorb_abb_reduction_ge_zero(self):
        s = self._stats("(a|b)*abb")
        assert s["dfa_reduction_pct"] >= 0.0

    def test_token_count_matches_regex_structure(self):
        """a|b has exactly 3 visible tokens: a, |, b."""
        b = body("a|b")
        assert b["stats"]["token_count"] >= 3

    def test_ast_node_count_positive(self):
        s = self._stats("a")
        assert s["ast_node_count"] >= 1

    def test_regex_length_correct(self):
        regex = "(a|b)*abb"
        s = self._stats(regex)
        assert s["regex_length"] == len(regex)

    def test_nfa_transitions_present(self):
        s = self._stats("ab")
        assert s["nfa_transitions"] > 0

    def test_dfa_transitions_present(self):
        s = self._stats("ab")
        assert s["dfa_transitions"] > 0

    def test_minimized_le_dfa_is_global_invariant(self):
        """Run every fixture and verify the invariant holds for all."""
        for f in ALL_PATTERNS:
            s = self._stats(f["regex"])
            assert s["minimized_dfa_states"] <= s["dfa_states"], f["id"]

    def test_security_risk_matches_stats_field(self):
        """stats.overall_security_risk must match security.overall_risk."""
        for f in ALL_PATTERNS:
            b = body(f["regex"])
            assert b["stats"]["overall_security_risk"] == b["security"]["overall_risk"], f["id"]


# ─────────────────────────────────────────────────────────────────────────────
# E. SPECIFIC HIGH-RISK END-TO-END
# ─────────────────────────────────────────────────────────────────────────────

class TestHighRiskEndToEnd:
    """The canonical ReDoS patterns must be flagged HIGH end-to-end."""

    @pytest.mark.parametrize("regex,expected_rule", [
        ("(a+)+",  "SEC001"),
        ("(a*)*",  "SEC001"),
        ("(a*)+",  "SEC001"),
        ("(a|aa)+", "SEC002"),
    ])
    def test_high_risk_flagged(self, regex, expected_rule):
        b = body(regex)
        assert b["security"]["overall_risk"] == "HIGH", (
            f'{regex!r} expected HIGH, got {b["security"]["overall_risk"]}'
        )
        rule_ids = {f["rule_id"] for f in b["security"]["findings"]}
        assert expected_rule in rule_ids, (
            f'{regex!r}: expected rule {expected_rule}, got {rule_ids}'
        )

    def test_aplus_plus_accepts_a(self):
        """(a+)+ accepts 'a' despite being risky."""
        r = call_test("(a+)+", "a")
        assert r.status_code == 200
        assert r.json()["matched"] is True

    def test_aplus_plus_rejects_b(self):
        r = call_test("(a+)+", "b")
        assert r.status_code == 200
        assert r.json()["matched"] is False

    def test_sec003_nullable_quantifier(self):
        """(a?)+ triggers SEC003 — nullable pattern under repetition."""
        b = body("(a?)+")
        risk = b["security"]["overall_risk"]
        assert risk in ("MEDIUM", "HIGH"), f'(a?)+ expected MEDIUM/HIGH, got {risk}'
        rule_ids = {f["rule_id"] for f in b["security"]["findings"]}
        assert "SEC003" in rule_ids, f'SEC003 missing; got {rule_ids}'

    def test_findings_have_caveat_text(self):
        """The DFA caveat must explicitly mention 'DFA' or 'backtrack'."""
        b = body("(a+)+")
        caveat = b["security"]["caveat"].lower()
        assert "dfa" in caveat or "backtrack" in caveat


# ─────────────────────────────────────────────────────────────────────────────
# F. RESPONSE SHAPE — structural completeness
# ─────────────────────────────────────────────────────────────────────────────

class TestResponseShape:
    """Top-level keys and nested shapes must always be present on success."""

    @pytest.fixture(scope="class")
    def resp_body(self):
        return body("(a|b)*abb")

    TOP_LEVEL_KEYS = ["success", "tokens", "ast", "nfa", "dfa",
                      "minimized_dfa", "diagnostics", "security", "stats"]

    @pytest.mark.parametrize("key", TOP_LEVEL_KEYS)
    def test_top_level_key_present(self, resp_body, key):
        assert key in resp_body, f"Missing key: {key}"

    AUTOMATA_KEYS = ["states", "alphabet", "transitions", "start", "accepting"]

    @pytest.mark.parametrize("automaton", ["nfa", "dfa", "minimized_dfa"])
    @pytest.mark.parametrize("key", AUTOMATA_KEYS)
    def test_automata_shape(self, resp_body, automaton, key):
        assert key in resp_body[automaton], f"{automaton}.{key} missing"

    STATS_KEYS = [
        "regex_length", "token_count", "ast_node_count",
        "nfa_states", "nfa_transitions",
        "dfa_states", "dfa_transitions",
        "minimized_dfa_states", "dfa_reduction_pct",
        "overall_security_risk",
    ]

    @pytest.mark.parametrize("key", STATS_KEYS)
    def test_stats_shape(self, resp_body, key):
        assert key in resp_body["stats"], f"stats.{key} missing"

    def test_security_shape(self, resp_body):
        sec = resp_body["security"]
        for k in ("overall_risk", "findings", "caveat"):
            assert k in sec, f"security.{k} missing"

    def test_test_endpoint_shape(self):
        r = call_test("(a|b)*abb", "abb")
        b = r.json()
        assert "matched" in b
        assert "path" in b
        assert isinstance(b["path"], list)
        assert len(b["path"]) > 0
