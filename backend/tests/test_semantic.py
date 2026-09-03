"""
Phase 3 — Semantic analyser tests.

Coverage targets
----------------
1.  Valid patterns produce empty diagnostic list
2.  SEM001: inverted range [z-a] → ERROR with correct code, message, position
3.  SEM001: multiple inverted ranges → one diagnostic per bad range
4.  SEM001: valid ranges [a-z] [0-9] → no SEM001
5.  SEM001: position correctly matches the start character column
6.  SEM002: consecutive quantifiers a** → WARNING
7.  SEM002: mixed consecutive a+? → WARNING
8.  SEM002: single quantifier a* → no SEM002
9.  SEM003: dot wildcard → ERROR with SEM003 code
10. SEM003: dot position reported correctly
11. SEM004: negated class [^a-z] → WARNING with SEM004 code
12. SEM004: non-negated class → no SEM004
13. has_errors() returns True when list contains ERROR
14. has_errors() returns False when only WARNINGs or empty
15. Diagnostic.to_dict() format: severity, code, message, position
16. Diagnostic.to_dict() omits position key when position is None
17. analyze() never raises (even on unusual input)
18. ERROR diagnostics prevent pipeline continuation (has_errors guard)
19. SEM001 message contains start and end character values
20. SEM002 is WARNING not ERROR
21. Multiple rules can fire on the same pattern
22. Deep nested tree all valid → empty list
"""

from __future__ import annotations

import json

import pytest

from app.ast import (
    CharClassNode,
    ClassRange,
    ConcatNode,
    DotNode,
    EpsilonNode,
    LiteralNode,
    PlusNode,
    QuestionNode,
    StarNode,
    UnionNode,
)
from app.parser  import parse_pattern
from app.semantic import Diagnostic, Severity, analyze, has_errors


# ── Convenience ───────────────────────────────────────────────────────────────

def diags(pattern: str) -> list[Diagnostic]:
    """Parse *pattern* and run the semantic analyser."""
    return analyze(parse_pattern(pattern))


def error_codes(pattern: str) -> list[str]:
    return [d.code for d in diags(pattern) if d.is_error]


def warning_codes(pattern: str) -> list[str]:
    return [d.code for d in diags(pattern) if not d.is_error]


# ─────────────────────────────────────────────────────────────────────────────
# 1. Valid patterns → no diagnostics
# ─────────────────────────────────────────────────────────────────────────────

class TestValidPatterns:

    @pytest.mark.parametrize("pattern", [
        "a",
        "abc",
        "a|b",
        "a*",
        "a+",
        "a?",
        "(a|b)*",
        "(a|b)*abb",
        "[a-z]",
        "[0-9]+",
        "[a-zA-Z0-9]",
        r"\(",
        r"\*",
    ])
    def test_valid_pattern_no_diagnostics(self, pattern):
        result = diags(pattern)
        assert result == [], (
            f"Expected no diagnostics for {pattern!r}, got: {result}"
        )

    def test_complex_valid_pattern(self):
        assert diags("(ab)+|[0-9]*") == []

    def test_nested_groups_valid(self):
        assert diags("((a|b)*c)+") == []


# ─────────────────────────────────────────────────────────────────────────────
# 2 & 3. SEM001 — Invalid character range
# ─────────────────────────────────────────────────────────────────────────────

class TestSEM001:

    def test_inverted_range_is_error(self):
        result = diags("[z-a]")
        assert any(d.code == "SEM001" and d.is_error for d in result)

    def test_inverted_range_code(self):
        result = diags("[z-a]")
        assert result[0].code == "SEM001"

    def test_inverted_range_severity_is_error(self):
        result = diags("[z-a]")
        assert result[0].severity is Severity.ERROR

    def test_inverted_range_message_contains_chars(self):
        result = diags("[z-a]")
        msg = result[0].message
        assert "z" in msg and "a" in msg

    def test_inverted_range_message_contains_codepoints(self):
        result = diags("[z-a]")
        msg = result[0].message
        # U+007A = z, U+0061 = a
        assert "007A" in msg or "0061" in msg

    def test_inverted_range_position_is_start_char(self):
        """For ``[z-a]``, 'z' is at column 2 (bracket at col 1)."""
        result = diags("[z-a]")
        assert result[0].position == 2

    def test_position_shifts_when_not_at_start(self):
        """In ``a[z-a]``, the bracket is at col 2, so 'z' is at col 3."""
        result = diags("a[z-a]")
        assert result[0].code == "SEM001"
        assert result[0].position == 3

    def test_multiple_inverted_ranges_one_diagnostic_each(self):
        """``[z-a9-0]`` has two bad ranges → two SEM001 diagnostics."""
        result = diags("[z-a9-0]")
        sem001 = [d for d in result if d.code == "SEM001"]
        assert len(sem001) == 2

    def test_valid_range_no_sem001(self):
        assert "SEM001" not in error_codes("[a-z]")

    def test_digit_range_no_sem001(self):
        assert "SEM001" not in error_codes("[0-9]")

    def test_single_char_class_no_sem001(self):
        assert "SEM001" not in error_codes("[x]")

    def test_uppercase_inverted(self):
        result = diags("[Z-A]")
        assert any(d.code == "SEM001" for d in result)

    def test_to_dict_has_position(self):
        result = diags("[z-a]")
        d = result[0].to_dict()
        assert "position" in d
        assert d["position"] == {"line": 1, "column": 2}

    def test_to_dict_json_serialisable(self):
        result = diags("[z-a]")
        # Must not raise
        payload = json.dumps([d.to_dict() for d in result])
        loaded = json.loads(payload)
        assert loaded[0]["code"] == "SEM001"
        assert loaded[0]["severity"] == "ERROR"


# ─────────────────────────────────────────────────────────────────────────────
# 6–8. SEM002 — Redundant consecutive quantifier
# ─────────────────────────────────────────────────────────────────────────────

class TestSEM002:

    def test_star_star_is_warning(self):
        result = diags("a**")
        assert any(d.code == "SEM002" and not d.is_error for d in result)

    def test_plus_question_is_warning(self):
        result = diags("a+?")
        assert any(d.code == "SEM002" for d in result)

    def test_question_star_is_warning(self):
        result = diags("a?*")
        assert any(d.code == "SEM002" for d in result)

    def test_sem002_is_warning_not_error(self):
        result = diags("a**")
        for d in result:
            if d.code == "SEM002":
                assert d.severity is Severity.WARNING

    def test_single_star_no_sem002(self):
        assert "SEM002" not in warning_codes("a*")

    def test_single_plus_no_sem002(self):
        assert "SEM002" not in warning_codes("a+")

    def test_sem002_message_mentions_quantifiers(self):
        result = diags("a**")
        for d in result:
            if d.code == "SEM002":
                assert "*" in d.message

    def test_sem002_position_is_outer_quantifier(self):
        """``a**``: outer ``*`` is at column 3."""
        result = diags("a**")
        sem002 = [d for d in result if d.code == "SEM002"]
        assert len(sem002) == 1
        assert sem002[0].position == 3

    def test_has_errors_false_for_only_sem002(self):
        result = diags("a**")
        assert not has_errors(result)


# ─────────────────────────────────────────────────────────────────────────────
# 9–10. SEM003 — Unsupported dot wildcard
# ─────────────────────────────────────────────────────────────────────────────

class TestSEM003:

    def test_dot_is_sem003_error(self):
        result = diags("a.b")
        assert any(d.code == "SEM003" and d.is_error for d in result)

    def test_dot_only_one_diagnostic(self):
        result = diags(".")
        sem003 = [d for d in result if d.code == "SEM003"]
        assert len(sem003) == 1

    def test_dot_position_reported(self):
        """In ``a.b`` the dot is at column 2."""
        result = diags("a.b")
        sem003 = [d for d in result if d.code == "SEM003"]
        assert sem003[0].position == 2

    def test_dot_at_start_position(self):
        result = diags(".")
        assert result[0].position == 1

    def test_dot_message_mentions_dot(self):
        result = diags(".")
        assert "." in result[0].message or "wildcard" in result[0].message.lower()

    def test_dot_is_error_not_warning(self):
        result = diags(".")
        assert result[0].severity is Severity.ERROR

    def test_no_dot_no_sem003(self):
        assert "SEM003" not in error_codes("abc")

    def test_has_errors_true_for_sem003(self):
        assert has_errors(diags("."))


# ─────────────────────────────────────────────────────────────────────────────
# 11–12. SEM004 — Negated character class
# ─────────────────────────────────────────────────────────────────────────────

class TestSEM004:

    def test_negated_class_is_warning(self):
        result = diags("[^a-z]")
        assert any(d.code == "SEM004" and not d.is_error for d in result)

    def test_negated_class_severity(self):
        result = diags("[^a-z]")
        for d in result:
            if d.code == "SEM004":
                assert d.severity is Severity.WARNING

    def test_negated_class_position_is_bracket(self):
        """``[^a-z]`` — ``[`` is at column 1."""
        result = diags("[^a-z]")
        for d in result:
            if d.code == "SEM004":
                assert d.position == 1

    def test_non_negated_class_no_sem004(self):
        assert "SEM004" not in warning_codes("[a-z]")

    def test_sem004_message_mentions_negation(self):
        result = diags("[^a-z]")
        for d in result:
            if d.code == "SEM004":
                assert "negat" in d.message.lower() or "^" in d.message

    def test_has_errors_false_for_only_sem004(self):
        assert not has_errors(diags("[^a-z]"))


# ─────────────────────────────────────────────────────────────────────────────
# 13–14. has_errors()
# ─────────────────────────────────────────────────────────────────────────────

class TestHasErrors:

    def test_empty_list_has_no_errors(self):
        assert not has_errors([])

    def test_only_errors(self):
        d = Diagnostic(Severity.ERROR, "SEM001", "bad range", 2)
        assert has_errors([d])

    def test_only_warnings(self):
        d = Diagnostic(Severity.WARNING, "SEM002", "redundant", 3)
        assert not has_errors([d])

    def test_mixed_errors_and_warnings(self):
        e = Diagnostic(Severity.ERROR,   "SEM003", "dot", 1)
        w = Diagnostic(Severity.WARNING, "SEM002", "redundant", 3)
        assert has_errors([w, e])

    def test_valid_pattern_no_errors(self):
        assert not has_errors(diags("(a|b)*abb"))


# ─────────────────────────────────────────────────────────────────────────────
# 15–16. Diagnostic.to_dict()
# ─────────────────────────────────────────────────────────────────────────────

class TestDiagnosticToDict:

    def test_error_fields(self):
        d = Diagnostic(Severity.ERROR, "SEM001", "bad range", 3)
        result = d.to_dict()
        assert result["severity"] == "ERROR"
        assert result["code"] == "SEM001"
        assert result["message"] == "bad range"
        assert result["position"] == {"line": 1, "column": 3}

    def test_warning_fields(self):
        d = Diagnostic(Severity.WARNING, "SEM002", "redundant", None)
        result = d.to_dict()
        assert result["severity"] == "WARNING"
        assert "position" not in result

    def test_no_position_key_when_none(self):
        d = Diagnostic(Severity.ERROR, "SEM999", "unknown", None)
        assert "position" not in d.to_dict()

    def test_is_error_property(self):
        assert Diagnostic(Severity.ERROR, "X", "m", None).is_error
        assert not Diagnostic(Severity.WARNING, "X", "m", None).is_error

    def test_json_round_trip(self):
        d = Diagnostic(Severity.ERROR, "SEM001", "bad", 5)
        obj = json.loads(json.dumps(d.to_dict()))
        assert obj["code"] == "SEM001"
        assert obj["position"]["column"] == 5


# ─────────────────────────────────────────────────────────────────────────────
# 17. analyze() never raises
# ─────────────────────────────────────────────────────────────────────────────

class TestNeverRaises:

    def test_literal_no_raise(self):
        analyze(LiteralNode("a"))

    def test_epsilon_no_raise(self):
        analyze(EpsilonNode())

    def test_dot_no_raise(self):
        analyze(DotNode(position=1))

    def test_char_class_no_raise(self):
        analyze(CharClassNode(False, (ClassRange("a", "z"),)))

    def test_inverted_char_class_no_raise(self):
        # SEM001 result — must not raise
        analyze(CharClassNode(False, (ClassRange("z", "a", start_pos=2),)))

    def test_star_no_raise(self):
        analyze(StarNode(LiteralNode("a"), position=2))

    def test_complex_tree_no_raise(self):
        from app.parser import parse_pattern
        ast = parse_pattern("(a|b)*abb")
        analyze(ast)


# ─────────────────────────────────────────────────────────────────────────────
# 18. Pipeline guard pattern
# ─────────────────────────────────────────────────────────────────────────────

class TestPipelineGuard:

    def test_error_pattern_stops_pipeline(self):
        """Callers must check has_errors() before continuing."""
        result = diags("[z-a]")
        if has_errors(result):
            # Pipeline would stop here
            assert True
        else:
            pytest.fail("Expected errors for [z-a]")

    def test_warning_pattern_allows_continuation(self):
        """SEM002 warning should not block the pipeline."""
        result = diags("a**")
        assert not has_errors(result), "SEM002 should not block continuation"

    def test_error_and_warning_blocks(self):
        result = diags(".[z-a]")
        assert has_errors(result)   # SEM001 + SEM003


# ─────────────────────────────────────────────────────────────────────────────
# 21. Multiple rules fire on same pattern
# ─────────────────────────────────────────────────────────────────────────────

class TestMultipleRules:

    def test_dot_and_inverted_range(self):
        """``.[z-a]`` → SEM003 (dot) + SEM001 (range)."""
        result = diags(".[z-a]")
        codes = {d.code for d in result}
        assert "SEM003" in codes
        assert "SEM001" in codes

    def test_sem001_and_sem004_together(self):
        """``[^z-a]`` → SEM004 (negated) + SEM001 (bad range)."""
        result = diags("[^z-a]")
        codes = {d.code for d in result}
        assert "SEM004" in codes
        assert "SEM001" in codes

    def test_warning_does_not_suppress_error(self):
        """SEM002 warning and SEM003 error both appear."""
        result = diags(".**")
        codes  = [d.code for d in result]
        assert "SEM003" in codes
        assert "SEM002" in codes


# ─────────────────────────────────────────────────────────────────────────────
# 22. Deep valid tree → empty list
# ─────────────────────────────────────────────────────────────────────────────

class TestDeepValidTree:

    @pytest.mark.parametrize("pattern", [
        "(a|b)*abb",
        "(ab)+|[0-9]*",
        "((a|b)*c)+[a-z]?",
        r"a\*b\|c",
    ])
    def test_no_diagnostics(self, pattern):
        assert diags(pattern) == []
