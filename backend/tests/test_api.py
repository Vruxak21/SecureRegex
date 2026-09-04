"""
Phase 8 — API integration tests (POST /api/analyze  and  POST /api/test).

Uses FastAPI's TestClient (via httpx) so no live server is needed.

Coverage targets
----------------
1.  Happy-path /analyze for (a|b)*abb — all top-level keys present
2.  Stats correctness for (a|b)*abb
3.  /analyze for (a+)+ — HIGH security risk in response
4.  Malformed regex — HTTP 4xx, structured error body, no raw traceback
5.  Oversized regex — rejected with REGEX_TOO_LONG
6.  /test match — (a|b)*abb correctly accepts 'abb'
7.  /test reject — correctly rejects 'ab'
8.  /test path starts at 0, ends at accepting state on match
9.  /test path terminates before end on reject
10. /test oversized input rejected
11. /test malformed regex → structured error
12. Content-Type and HTTP status checks
13. Security finding fields complete for (a+)+
14. NFA/DFA/minimized_dfa shape validation
15. Token list non-empty for valid pattern
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app, raise_server_exceptions=False)

ANALYZE = "/api/v1/analyze"
TEST    = "/api/v1/test"


# ── Helpers ───────────────────────────────────────────────────────────────────

def analyze(regex: str):
    return client.post(ANALYZE, json={"regex": regex})

def call_test(regex: str, inp: str):
    return client.post(TEST, json={"regex": regex, "input": inp})


# ─────────────────────────────────────────────────────────────────────────────
# 1 & 2.  Happy-path /analyze — (a|b)*abb
# ─────────────────────────────────────────────────────────────────────────────

class TestAnalyzeHappyPath:
    """Full pipeline response for the canonical pattern (a|b)*abb."""

    @pytest.fixture(scope="class")
    def resp(self):
        return analyze("(a|b)*abb")

    @pytest.fixture(scope="class")
    def body(self, resp):
        return resp.json()

    def test_http_200(self, resp):
        assert resp.status_code == 200

    def test_success_true(self, body):
        assert body["success"] is True

    # Top-level keys
    @pytest.mark.parametrize("key", [
        "success", "tokens", "ast", "nfa", "dfa",
        "minimized_dfa", "diagnostics", "security", "stats",
    ])
    def test_top_level_key_present(self, body, key):
        assert key in body, f"Missing key: {key!r}"

    # Tokens
    def test_tokens_non_empty(self, body):
        assert len(body["tokens"]) > 0

    def test_token_has_type_value_column(self, body):
        for t in body["tokens"]:
            assert "type"   in t
            assert "value"  in t
            assert "column" in t

    # AST
    def test_ast_has_type(self, body):
        assert "type" in body["ast"]

    def test_ast_root_is_concat(self, body):
        assert body["ast"]["type"] == "Concat"

    # NFA
    def test_nfa_keys(self, body):
        nfa = body["nfa"]
        for k in ("states", "alphabet", "transitions", "start", "accepting"):
            assert k in nfa

    def test_nfa_14_states(self, body):
        assert len(body["nfa"]["states"]) == 14

    def test_nfa_has_epsilon_transitions(self, body):
        symbols = {t["symbol"] for t in body["nfa"]["transitions"]}
        assert "ε" in symbols

    # DFA
    def test_dfa_5_states(self, body):
        assert len(body["dfa"]["states"]) == 5

    def test_dfa_10_transitions(self, body):
        assert len(body["dfa"]["transitions"]) == 10

    def test_dfa_start_zero(self, body):
        assert body["dfa"]["start"] == 0

    def test_dfa_no_epsilon(self, body):
        symbols = {t["symbol"] for t in body["dfa"]["transitions"]}
        assert "ε" not in symbols

    # Minimized DFA
    def test_min_dfa_4_states(self, body):
        assert len(body["minimized_dfa"]["states"]) == 4

    def test_min_dfa_start_zero(self, body):
        assert body["minimized_dfa"]["start"] == 0

    def test_min_dfa_one_accepting(self, body):
        assert len(body["minimized_dfa"]["accepting"]) == 1

    # Security
    def test_security_overall_none(self, body):
        assert body["security"]["overall_risk"] == "NONE"

    def test_security_findings_empty(self, body):
        assert body["security"]["findings"] == []

    def test_security_caveat_present(self, body):
        assert len(body["security"]["caveat"]) > 20

    # Diagnostics
    def test_diagnostics_empty(self, body):
        assert body["diagnostics"] == []

    # Stats
    def test_stats_regex_length(self, body):
        assert body["stats"]["regex_length"] == 9

    def test_stats_token_count(self, body):
        assert body["stats"]["token_count"] == 9

    def test_stats_nfa_states(self, body):
        assert body["stats"]["nfa_states"] == 14

    def test_stats_dfa_states(self, body):
        assert body["stats"]["dfa_states"] == 5

    def test_stats_minimized_dfa_states(self, body):
        assert body["stats"]["minimized_dfa_states"] == 4

    def test_stats_reduction_pct(self, body):
        assert body["stats"]["dfa_reduction_pct"] == 20.0

    def test_stats_security_risk_none(self, body):
        assert body["stats"]["overall_security_risk"] == "NONE"

    def test_stats_all_keys_present(self, body):
        stats = body["stats"]
        expected_keys = {
            "regex_length", "token_count", "ast_node_count",
            "nfa_states", "nfa_transitions",
            "dfa_states", "dfa_transitions",
            "minimized_dfa_states", "dfa_reduction_pct",
            "overall_security_risk",
        }
        assert set(stats.keys()) == expected_keys


# ─────────────────────────────────────────────────────────────────────────────
# 3.  /analyze for (a+)+ — HIGH risk
# ─────────────────────────────────────────────────────────────────────────────

class TestAnalyzeHighRisk:

    @pytest.fixture(scope="class")
    def body(self):
        return analyze("(a+)+").json()

    def test_http_200(self):
        assert analyze("(a+)+").status_code == 200

    def test_success_true(self, body):
        assert body["success"] is True

    def test_security_overall_high(self, body):
        assert body["security"]["overall_risk"] == "HIGH"

    def test_security_finding_sec001(self, body):
        rule_ids = [f["rule_id"] for f in body["security"]["findings"]]
        assert "SEC001" in rule_ids

    def test_sec001_finding_has_all_fields(self, body):
        f = next(f for f in body["security"]["findings"] if f["rule_id"] == "SEC001")
        for field in ("rule_id", "risk_level", "title", "reason", "explanation",
                      "recommendation", "location"):
            assert field in f, f"Missing field {field!r} in SEC001 finding"

    def test_sec001_risk_level_high(self, body):
        f = next(f for f in body["security"]["findings"] if f["rule_id"] == "SEC001")
        assert f["risk_level"] == "HIGH"

    def test_stats_security_risk_high(self, body):
        assert body["stats"]["overall_security_risk"] == "HIGH"


# ─────────────────────────────────────────────────────────────────────────────
# 4.  Malformed regex — structured error, HTTP 4xx, no raw traceback
# ─────────────────────────────────────────────────────────────────────────────

class TestAnalyzeMalformed:

    @pytest.mark.parametrize("bad_regex", [
        "(",          # unclosed group → ParseError
        ")",          # unexpected closing paren
        "[",          # unclosed char class → ParseError/LexerError
        "(a|)",       # empty alternation arm → ParseError
    ])
    def test_bad_regex_4xx(self, bad_regex):
        r = analyze(bad_regex)
        assert 400 <= r.status_code < 500, (
            f"Expected 4xx for {bad_regex!r}, got {r.status_code}"
        )

    @pytest.mark.parametrize("bad_regex", [
        "(",
        ")",
        "[",
    ])
    def test_body_has_error_field(self, bad_regex):
        body = analyze(bad_regex).json()
        assert "error" in body, f"No 'error' key in response for {bad_regex!r}"

    @pytest.mark.parametrize("bad_regex", [
        "(",
        ")",
    ])
    def test_body_has_message(self, bad_regex):
        body = analyze(bad_regex).json()
        assert "message" in body
        assert isinstance(body["message"], str)
        assert len(body["message"]) > 0

    def test_no_traceback_in_response(self):
        body = analyze("(").json()
        body_str = str(body)
        assert "Traceback" not in body_str
        assert "File \"" not in body_str

    def test_invalid_char_class_range_has_diagnostics(self):
        # [z-a] passes lexer+parser but fails semantic analysis.
        # Pipeline returns HTTP 200 with success=True and ERROR diagnostics in body.
        r = analyze("[z-a]")
        body = r.json()
        assert r.status_code == 200
        assert any(d["severity"] == "ERROR" for d in body["diagnostics"])

    def test_semantic_error_diagnostic_code_sem001(self):
        body = analyze("[z-a]").json()
        codes = [d["code"] for d in body["diagnostics"]]
        assert "SEM001" in codes


# ─────────────────────────────────────────────────────────────────────────────
# 5.  Oversized regex — rejected cleanly
# ─────────────────────────────────────────────────────────────────────────────

class TestOversizedInput:

    def test_oversized_regex_rejected(self):
        huge = "a" * 10_001
        r = analyze(huge)
        assert r.status_code == 422

    def test_oversized_regex_error_code(self):
        huge = "a" * 10_001
        body = analyze(huge).json()
        assert body.get("error") == "REGEX_TOO_LONG"

    def test_oversized_regex_message_present(self):
        body = analyze("a" * 10_001).json()
        assert "message" in body
        assert len(body["message"]) > 0


# ─────────────────────────────────────────────────────────────────────────────
# 6–9.  /api/test — match + reject + path
# ─────────────────────────────────────────────────────────────────────────────

class TestEndpointMatch:
    """(a|b)*abb match and reject tests with path validation."""

    @pytest.mark.parametrize("inp", ["abb", "aabb", "babb", "ababb", "abababb"])
    def test_accepts_valid_strings(self, inp):
        body = call_test("(a|b)*abb", inp).json()
        assert body["matched"] is True, f"Expected 'abb'-family string {inp!r} to match"

    @pytest.mark.parametrize("inp", ["", "ab", "a", "b", "abba", "abc"])
    def test_rejects_invalid_strings(self, inp):
        body = call_test("(a|b)*abb", inp).json()
        assert body["matched"] is False, f"Expected {inp!r} to be rejected"

    def test_path_starts_at_zero(self):
        body = call_test("(a|b)*abb", "abb").json()
        assert body["path"][0] == 0

    def test_path_ends_at_accepting_on_match(self):
        min_body = analyze("(a|b)*abb").json()
        accepting = set(min_body["minimized_dfa"]["accepting"])
        path = call_test("(a|b)*abb", "abb").json()["path"]
        assert path[-1] in accepting, (
            f"Path ended at {path[-1]}, expected one of {accepting}"
        )

    def test_path_length_equals_input_plus_one_on_match(self):
        inp = "abb"
        body = call_test("(a|b)*abb", inp).json()
        assert len(body["path"]) == len(inp) + 1

    def test_path_length_le_input_plus_one_on_reject(self):
        inp = "abba"
        body = call_test("(a|b)*abb", inp).json()
        assert len(body["path"]) <= len(inp) + 1

    def test_path_non_empty(self):
        body = call_test("(a|b)*abb", "abb").json()
        assert len(body["path"]) > 0

    def test_path_all_integers(self):
        body = call_test("(a|b)*abb", "abb").json()
        assert all(isinstance(s, int) for s in body["path"])

    def test_simple_literal_accepts(self):
        body = call_test("a", "a").json()
        assert body["matched"] is True

    def test_simple_literal_rejects(self):
        body = call_test("a", "b").json()
        assert body["matched"] is False

    def test_http_200_on_match(self):
        assert call_test("(a|b)*abb", "abb").status_code == 200

    def test_http_200_on_reject(self):
        assert call_test("(a|b)*abb", "xyz").status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# 10.  /test oversized input rejected
# ─────────────────────────────────────────────────────────────────────────────

class TestOversizedTestInput:

    def test_oversized_input_rejected(self):
        r = call_test("a", "a" * 100_001)
        assert r.status_code in {422, 400}

    def test_oversized_input_error_code(self):
        body = call_test("a", "a" * 100_001).json()
        assert body.get("error") == "INPUT_TOO_LONG"

    def test_oversized_regex_in_test_rejected(self):
        r = call_test("a" * 10_001, "a")
        assert r.status_code == 422


# ─────────────────────────────────────────────────────────────────────────────
# 11.  /test malformed regex → structured error
# ─────────────────────────────────────────────────────────────────────────────

class TestMalformedInTestEndpoint:

    def test_malformed_regex_4xx(self):
        r = call_test("(", "abc")
        assert 400 <= r.status_code < 500

    def test_malformed_regex_has_error_field(self):
        body = call_test("(", "abc").json()
        assert "error" in body

    def test_no_traceback_on_parse_error(self):
        body = str(call_test("(", "abc").json())
        assert "Traceback" not in body


# ─────────────────────────────────────────────────────────────────────────────
# 12.  Content-Type and status
# ─────────────────────────────────────────────────────────────────────────────

class TestContentType:

    def test_analyze_content_type_json(self):
        r = analyze("a")
        assert "application/json" in r.headers["content-type"]

    def test_test_content_type_json(self):
        r = call_test("a", "a")
        assert "application/json" in r.headers["content-type"]

    def test_analyze_missing_body_422(self):
        r = client.post(ANALYZE, json={})
        assert r.status_code == 422

    def test_test_missing_body_422(self):
        r = client.post(TEST, json={})
        assert r.status_code == 422

    def test_analyze_extra_field_rejected(self):
        r = client.post(ANALYZE, json={"regex": "a", "extra": "oops"})
        assert r.status_code == 422


# ─────────────────────────────────────────────────────────────────────────────
# 13.  NFA/DFA/minimized_dfa shape
# ─────────────────────────────────────────────────────────────────────────────

class TestAutomataShape:

    @pytest.fixture(scope="class")
    def body(self):
        return analyze("(a|b)*abb").json()

    @pytest.mark.parametrize("key", ["states", "alphabet", "transitions", "start", "accepting"])
    def test_nfa_has_key(self, body, key):
        assert key in body["nfa"]

    @pytest.mark.parametrize("key", ["states", "alphabet", "transitions", "start", "accepting"])
    def test_dfa_has_key(self, body, key):
        assert key in body["dfa"]

    @pytest.mark.parametrize("key", ["states", "alphabet", "transitions", "start", "accepting"])
    def test_min_dfa_has_key(self, body, key):
        assert key in body["minimized_dfa"]

    def test_dfa_transitions_have_from_symbol_to(self, body):
        for t in body["dfa"]["transitions"]:
            assert "from"   in t
            assert "symbol" in t
            assert "to"     in t

    def test_min_dfa_le_dfa_states(self, body):
        assert len(body["minimized_dfa"]["states"]) <= len(body["dfa"]["states"])


# ─────────────────────────────────────────────────────────────────────────────
# 14.  Various valid patterns round-trip
# ─────────────────────────────────────────────────────────────────────────────

class TestVariousPatterns:

    @pytest.mark.parametrize("pattern", [
        "a", "ab", "a|b", "a*", "a+", "a?",
        "[a-z]+", "[0-9]*",
    ])
    def test_valid_pattern_200(self, pattern):
        assert analyze(pattern).status_code == 200

    @pytest.mark.parametrize("pattern", [
        "a", "ab", "a|b", "a*", "a+", "a?",
        "[a-z]+", "[0-9]*",
    ])
    def test_valid_pattern_success_true(self, pattern):
        body = analyze(pattern).json()
        assert body.get("success") is True
