"""
Phase 7 — ReDoS Security Analyzer tests.

Rule coverage
-------------
SEC001  Nested Quantifiers         (HIGH)
SEC002  Overlapping Alternation    (HIGH or MEDIUM)
SEC003  Nullable Repetition        (MEDIUM)

Known limitations documented as test cases
------------------------------------------
LIMIT01 (ab|ac)+  — SEC002 MEDIUM (false positive — second char disambiguates)
LIMIT02 (a|b)+    — correctly NOT flagged (disjoint first chars)
LIMIT03 (a|b)*abb — correctly NONE overall (safe pattern)

Structure of test classes
--------------------------
TestSEC001         - nested quantifier detection
TestSEC002         - overlapping alternation detection
TestSEC003         - nullable repetition detection
TestSafePatterns   - patterns that must NOT be flagged (false-positive guard)
TestReportStructure - JSON shape, caveat, to_dict
TestOverallRisk    - overall_risk aggregation
TestKnownLimitations - boundary/tricky cases with documented rationale
TestRiskLevels     - ordering, comparison helpers
"""

from __future__ import annotations

import json

import pytest

from app.parser   import parse_pattern
from app.security import (
    HIGH, MEDIUM, NONE,
    SecurityFinding, SecurityReport,
    analyze_security,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def report(pattern: str) -> SecurityReport:
    return analyze_security(parse_pattern(pattern))


def has_rule(r: SecurityReport, rule_id: str) -> bool:
    return any(f.rule_id == rule_id for f in r.findings)


def risk_of(r: SecurityReport, rule_id: str) -> str | None:
    for f in r.findings:
        if f.rule_id == rule_id:
            return f.risk_level
    return None


# ─────────────────────────────────────────────────────────────────────────────
# SEC001 — Nested Quantifiers
# ─────────────────────────────────────────────────────────────────────────────

class TestSEC001:
    """Nested Star/Plus under Star/Plus must fire SEC001 at HIGH."""

    @pytest.mark.parametrize("pattern", [
        "(a+)+",      # classic: plus under plus
        "(a*)*",      # star under star
        "(a*)+",      # star under plus
        "(a+)*",      # plus under star
        "([a-z]+)+",  # char-class plus under plus
        "((ab)+)+",   # concat group under plus
        "(b(a+))*",   # plus inside concat under star
    ])
    def test_sec001_fires(self, pattern):
        r = report(pattern)
        assert has_rule(r, "SEC001"), f"Expected SEC001 for {pattern!r}"

    @pytest.mark.parametrize("pattern", [
        "(a+)+",
        "(a*)*",
        "([a-z]+)+",
    ])
    def test_sec001_is_high(self, pattern):
        assert risk_of(report(pattern), "SEC001") == HIGH

    def test_sec001_location_present(self):
        r = report("(a+)+")
        f = next(f for f in r.findings if f.rule_id == "SEC001")
        # Location may be None if position not tracked, but if present must be a 2-tuple
        if f.location is not None:
            start, end = f.location
            assert isinstance(start, int)
            assert isinstance(end, int)

    def test_sec001_reason_mentions_quantifier(self):
        r = report("(a+)+")
        f = next(f for f in r.findings if f.rule_id == "SEC001")
        assert "+" in f.reason or "*" in f.reason

    def test_sec001_recommendation_mentions_simplification(self):
        f = next(f for f in report("(a+)+").findings if f.rule_id == "SEC001")
        assert "a+" in f.recommendation or "simplif" in f.recommendation.lower()

    def test_sec001_overall_risk_is_high(self):
        assert report("(a+)+").overall_risk == HIGH

    def test_nested_char_class_high(self):
        # ([a-z]+)+ is a common ReDoS pattern in the wild
        r = report("([a-z]+)+")
        assert has_rule(r, "SEC001")
        assert r.overall_risk == HIGH

    def test_deeply_nested(self):
        # ((a+)+)+ — should still produce SEC001
        r = report("((a+)+)+")
        assert has_rule(r, "SEC001")


# ─────────────────────────────────────────────────────────────────────────────
# SEC002 — Overlapping Alternation in Repetition
# ─────────────────────────────────────────────────────────────────────────────

class TestSEC002:
    """Alternation with shared first-chars under Star/Plus must fire SEC002."""

    def test_a_or_aa_plus_fires_high(self):
        r = report("(a|aa)+")
        assert has_rule(r, "SEC002")
        assert risk_of(r, "SEC002") == HIGH

    def test_a_or_aa_star_fires_high(self):
        r = report("(a|aa)*")
        assert has_rule(r, "SEC002")
        assert risk_of(r, "SEC002") == HIGH

    def test_a_or_aplus_plus_fires_high(self):
        # (a|a+b)+ — 'a' is prefix of 'a+b' language
        r = report("(a|a+b)+")
        assert has_rule(r, "SEC002")

    def test_sec002_overall_at_least_medium(self):
        r = report("(a|aa)+")
        from app.security.report import RISK_ORDER
        assert RISK_ORDER.index(r.overall_risk) >= RISK_ORDER.index("MEDIUM")

    def test_reason_mentions_overlap(self):
        r = report("(a|aa)+")
        f = next(f for f in r.findings if f.rule_id == "SEC002")
        assert "'" in f.reason or "char" in f.reason.lower() or "a" in f.reason

    def test_explanation_mentions_backtracking(self):
        f = next(f for f in report("(a|aa)+").findings if f.rule_id == "SEC002")
        assert "backtrack" in f.explanation.lower()

    def test_recommendation_present(self):
        f = next(f for f in report("(a|aa)+").findings if f.rule_id == "SEC002")
        assert len(f.recommendation) > 10

    def test_multiple_branches(self):
        # (a|aa|aaa)+ — three overlapping branches
        r = report("(a|aa|aaa)+")
        assert has_rule(r, "SEC002")


# ─────────────────────────────────────────────────────────────────────────────
# SEC003 — Repetition Over Nullable Expression
# ─────────────────────────────────────────────────────────────────────────────

class TestSEC003:
    """Star/Plus over a nullable (can-match-ε) child must fire SEC003."""

    def test_optional_under_plus(self):
        # (a?)+ — a? is nullable
        r = report("(a?)+")
        assert has_rule(r, "SEC003")
        assert risk_of(r, "SEC003") == MEDIUM

    def test_optional_under_star(self):
        r = report("(a?)*")
        assert has_rule(r, "SEC003")

    def test_star_under_plus_gives_sec001_not_sec003(self):
        # (a*)+ — SEC001 should fire (and suppress SEC003 for same position)
        r = report("(a*)+")
        assert has_rule(r, "SEC001")
        # SEC003 should NOT duplicate (same position already covered)
        sec001_positions = {f.location for f in r.findings if f.rule_id == "SEC001"}
        sec003_positions = {f.location for f in r.findings if f.rule_id == "SEC003"}
        # There should be no SEC003 at the same position as SEC001
        assert not (sec001_positions & sec003_positions)

    def test_sec003_recommendation_mentions_rewrite(self):
        f = next(f for f in report("(a?)+").findings if f.rule_id == "SEC003")
        assert "a*" in f.recommendation or "rewrite" in f.recommendation.lower()


# ─────────────────────────────────────────────────────────────────────────────
# Safe patterns — must NOT produce HIGH or MEDIUM findings
# ─────────────────────────────────────────────────────────────────────────────

class TestSafePatterns:
    """These patterns must not be flagged as HIGH or MEDIUM risk."""

    @pytest.mark.parametrize("pattern", [
        "a",
        "ab",
        "a|b",
        "a*",
        "a+",
        "a?",
        "[a-z]",
        "[0-9]+",
        "(a|b)*abb",   # canonical safe pattern — requirement
        "(a|b)+",      # disjoint first chars — safe
        "(ab)+",       # single fixed-length branch — safe
        "a*b+c?",
        "[a-z]+[0-9]*",
    ])
    def test_safe_pattern_not_high(self, pattern):
        r = report(pattern)
        assert r.overall_risk != HIGH, (
            f"Pattern {pattern!r} was incorrectly flagged HIGH. "
            f"Findings: {[f.rule_id for f in r.findings]}"
        )

    def test_canonical_safe_is_none(self):
        """(a|b)*abb is the canonical safe example from the requirements."""
        r = report("(a|b)*abb")
        assert r.overall_risk == NONE, (
            f"(a|b)*abb should be NONE, got {r.overall_risk}. "
            f"Findings: {[f.rule_id for f in r.findings]}"
        )

    def test_no_findings_for_literal(self):
        assert len(report("a").findings) == 0

    def test_no_findings_for_simple_star(self):
        # a* — outer star but no inner star/plus → no SEC001
        assert not has_rule(report("a*"), "SEC001")

    def test_aorb_plus_not_flagged_sec002(self):
        # (a|b)+ — disjoint first chars → no SEC002
        assert not has_rule(report("(a|b)+"), "SEC002")


# ─────────────────────────────────────────────────────────────────────────────
# Report structure and JSON
# ─────────────────────────────────────────────────────────────────────────────

class TestReportStructure:
    """Every report must have the required fields and be JSON-serialisable."""

    def test_to_dict_keys(self):
        d = report("(a+)+").to_dict()
        assert set(d.keys()) == {"overall_risk", "findings", "caveat"}

    def test_caveat_always_present(self):
        for pattern in ["a", "(a+)+", "(a|b)*abb"]:
            r = report(pattern)
            assert r.caveat, f"caveat missing for {pattern!r}"
            assert len(r.caveat) > 20

    def test_caveat_mentions_dfa(self):
        assert "DFA" in report("a").caveat

    def test_caveat_mentions_backtrack(self):
        assert "backtrack" in report("a").caveat.lower()

    def test_caveat_says_potential_not_confirmed(self):
        caveat = report("(a+)+").caveat.lower()
        assert "potential" in caveat or "indicator" in caveat

    def test_finding_dict_keys(self):
        findings = report("(a+)+").to_dict()["findings"]
        assert len(findings) >= 1
        f = findings[0]
        for key in ("rule_id", "risk_level", "title", "reason",
                    "explanation", "recommendation", "location"):
            assert key in f, f"Missing key: {key!r}"

    def test_json_serialisable_safe(self):
        json.dumps(report("(a|b)*abb").to_dict())

    def test_json_serialisable_dangerous(self):
        json.dumps(report("(a+)+").to_dict())

    def test_findings_is_tuple(self):
        r = report("(a+)+")
        assert isinstance(r.findings, tuple)

    def test_empty_findings_for_safe(self):
        r = report("(a|b)*abb")
        assert r.findings == ()

    def test_finding_risk_level_valid(self):
        for f in report("(a+)+").findings:
            assert f.risk_level in {HIGH, MEDIUM, "LOW"}

    def test_finding_rule_id_format(self):
        for f in report("(a+)+").findings:
            assert f.rule_id.startswith("SEC")
            assert f.rule_id[3:].isdigit()


# ─────────────────────────────────────────────────────────────────────────────
# Overall risk aggregation
# ─────────────────────────────────────────────────────────────────────────────

class TestOverallRisk:

    def test_none_when_no_findings(self):
        assert report("ab").overall_risk == NONE

    def test_high_when_sec001_fires(self):
        assert report("(a+)+").overall_risk == HIGH

    def test_high_when_sec002_fires_high(self):
        assert report("(a|aa)+").overall_risk == HIGH

    def test_medium_for_optional_loop(self):
        # (a?)+ → SEC003 MEDIUM (no SEC001 since ? is not Star/Plus)
        r = report("(a?)+")
        assert r.overall_risk == MEDIUM

    def test_high_beats_medium(self):
        # Pattern with both SEC001 and SEC003 — HIGH wins
        r = report("(a*)+")        # SEC001 HIGH (a* under +)
        assert r.overall_risk == HIGH


# ─────────────────────────────────────────────────────────────────────────────
# Known limitations / tricky boundary cases
# ─────────────────────────────────────────────────────────────────────────────

class TestKnownLimitations:
    """
    LIMIT01: (ab|ac)+
        SEC002 MEDIUM fires because FIRST('ab') ∩ FIRST('ac') = {'a'}.
        However this pattern is NOT exponentially backtracking in practice —
        the second character disambiguates ('b' vs 'c').
        This is a KNOWN FALSE POSITIVE; documented in docs/security-analysis.md.

    LIMIT02: (a|b)+
        Correctly NOT flagged. FIRST('a') ∩ FIRST('b') = ∅.

    LIMIT03: (a|b)*abb
        Correctly NONE. The (a|b)* part has disjoint first chars.

    LIMIT04: (a+b)+
        Contains '+' under '+' but the inner '+' matches 'a' and the outer
        boundary is forced by the mandatory 'b'. This IS flagged by SEC001
        (conservative) — documented as a potential false positive because
        '(a+b)+' on 'aaabaaabX' has polynomial not exponential backtracking.
        Phrased as HIGH because it is structurally indistinguishable from
        truly dangerous patterns without deeper analysis.
    """

    def test_limit01_ab_or_ac_plus_fires_sec002_medium(self):
        """(ab|ac)+ — false positive; documented limitation."""
        r = report("(ab|ac)+")
        assert has_rule(r, "SEC002")
        assert risk_of(r, "SEC002") == MEDIUM   # lower confidence: not a clear prefix

    def test_limit02_aorb_plus_clean(self):
        """(a|b)+ — correctly not flagged (disjoint first chars)."""
        r = report("(a|b)+")
        assert not has_rule(r, "SEC002")

    def test_limit03_canonical_safe_none(self):
        """(a|b)*abb — the canonical safe pattern from the requirements."""
        r = report("(a|b)*abb")
        assert r.overall_risk == NONE

    def test_limit04_a_plus_b_plus_flagged_high(self):
        """(a+b)+ — conservative flag (polynomial in practice, documented)."""
        r = report("(a+b)+")
        assert has_rule(r, "SEC001")
        assert r.overall_risk == HIGH


# ─────────────────────────────────────────────────────────────────────────────
# Specific requirement: (a+)+ full report JSON check
# ─────────────────────────────────────────────────────────────────────────────

class TestRequirementPatterns:
    """Explicit checks from the Phase 7 requirements."""

    def test_aplus_plus_high_with_correct_rule(self):
        r = report("(a+)+")
        assert r.overall_risk == HIGH
        assert has_rule(r, "SEC001")

    def test_aplus_plus_location_at_outer_quantifier(self):
        r = report("(a+)+")
        f = next(f for f in r.findings if f.rule_id == "SEC001")
        # Outer '+' is at column 5 (1-indexed): ( a + ) +
        if f.location is not None:
            assert f.location[0] == 5, (
                f"Expected outer '+' at column 5, got {f.location}"
            )

    def test_a_or_aa_plus_at_least_medium(self):
        r = report("(a|aa)+")
        assert r.overall_risk in {HIGH, MEDIUM}
        assert any(f.rule_id in {"SEC001", "SEC002"} for f in r.findings)

    def test_canonical_safe_none(self):
        r = report("(a|b)*abb")
        assert r.overall_risk == NONE
        assert r.findings == ()
