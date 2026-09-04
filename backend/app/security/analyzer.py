"""
ReDoS heuristic analyzer — walks the AST and applies structural detection rules.

Heuristic Rules
---------------
SEC001  Nested Quantifiers (HIGH)
    Trigger : A Star/Plus whose child subtree contains another Star or Plus.
    Rationale: The inner loop competes with the outer loop for the same input
               characters, allowing exponentially many partitions.
    Example : ``(a+)+``, ``(a*)*``, ``([a-z]+)+``

SEC002  Overlapping Alternation in Repetition (HIGH or MEDIUM)
    Trigger : A Star/Plus wrapping a Union where ≥ 2 branches share first
              characters (FIRST(X) ∩ FIRST(Y) ≠ ∅).
    HIGH    : when one branch is a language-prefix of another (e.g. ``a`` and
              ``aa`` — the engine cannot decide at which iteration to stop).
    MEDIUM  : first-char overlap without a clear prefix relationship
              (e.g. ``(ab|ac)+`` — a possible false positive; documented below).
    Example : ``(a|aa)+``, ``(a|a+b)+``

SEC003  Repetition Over Nullable Expression (MEDIUM)
    Trigger : A Star/Plus whose child can match the empty string (ε) and is not
              a plain EpsilonNode.  SEC001 supersedes this when it already fires.
    Rationale: An inner ε-match causes the outer loop to spin potentially
               forever (zero-width match loop) in backtracking engines.
    Example : ``(a?)+``, ``(a|ε)*``

False-positive / false-negative caveats (see docs/security-analysis.md)
------------------------------------------------------------------------
* SEC002 at MEDIUM may fire on ``(ab|ac)+`` where the second character
  disambiguates the branches — this is NOT catastrophically backtracking
  but is flagged as a precaution.
* Patterns built from nested CharClassNodes (e.g. ``([a-z][0-9]+)+``) trigger
  SEC001 correctly, but the severity is always HIGH regardless of whether the
  character classes overlap.
* ``(a?)+`` triggers SEC003 but can be trivially rewritten as ``a*``.
* Quantified alternation like ``(a|b)+`` does NOT trigger SEC002 because
  FIRST('a') ∩ FIRST('b') = ∅.
"""

from __future__ import annotations

from app.ast.nodes import (
    ASTNode,
    ConcatNode, UnionNode,
    StarNode, PlusNode, QuestionNode,
    LiteralNode, EpsilonNode, DotNode, CharClassNode,
)
from app.security.report import (
    SecurityFinding, SecurityReport,
    HIGH, MEDIUM, LOW, NONE, RISK_ORDER, CAVEAT,
)


# ── AST utilities ──────────────────────────────────────────────────────────────

def _children(node: ASTNode) -> list[ASTNode]:
    """Direct children of *node* for generic tree traversal."""
    if isinstance(node, (ConcatNode, UnionNode)):
        return [node.left, node.right]         # type: ignore[attr-defined]
    if isinstance(node, (StarNode, PlusNode, QuestionNode)):
        return [node.child]                    # type: ignore[attr-defined]
    return []


def _subtree_has_star_or_plus(node: ASTNode) -> bool:
    """True if *node* or any descendant is a StarNode or PlusNode."""
    if isinstance(node, (StarNode, PlusNode)):
        return True
    return any(_subtree_has_star_or_plus(c) for c in _children(node))


def _is_nullable(node: ASTNode) -> bool:
    """True if *node* can match the empty string (ε)."""
    if isinstance(node, EpsilonNode):
        return True
    if isinstance(node, (StarNode, QuestionNode)):
        return True
    if isinstance(node, PlusNode):
        return _is_nullable(node.child)           # type: ignore[attr-defined]
    if isinstance(node, ConcatNode):
        return _is_nullable(node.left) and _is_nullable(node.right)
    if isinstance(node, UnionNode):
        return _is_nullable(node.left) or _is_nullable(node.right)
    return False   # Literal, Dot, CharClass


def _first_chars(node: ASTNode) -> frozenset[str]:
    """Return the set of characters *node* can produce as its FIRST character."""
    if isinstance(node, LiteralNode):
        return frozenset({node.char})
    if isinstance(node, CharClassNode):
        chars: set[str] = set()
        for r in node.ranges:
            for cp in range(ord(r.start), ord(r.end) + 1):
                chars.add(chr(cp))
        if node.negate:
            # Conservative: negated class matches many chars — treat as ALL
            all_printable = frozenset(chr(i) for i in range(0x20, 0x7F))
            return all_printable - chars
        return frozenset(chars)
    if isinstance(node, ConcatNode):
        fc = _first_chars(node.left)
        if _is_nullable(node.left):
            fc = fc | _first_chars(node.right)
        return fc
    if isinstance(node, UnionNode):
        return _first_chars(node.left) | _first_chars(node.right)
    if isinstance(node, (StarNode, QuestionNode, PlusNode)):
        return _first_chars(node.child)           # type: ignore[attr-defined]
    if isinstance(node, EpsilonNode):
        return frozenset()
    if isinstance(node, DotNode):
        return frozenset(chr(i) for i in range(0x20, 0x7F))
    return frozenset()


def _collect_union_branches(node: ASTNode) -> list[ASTNode]:
    """Flatten nested UnionNodes into a flat list of alternatives."""
    if isinstance(node, UnionNode):
        return _collect_union_branches(node.left) + _collect_union_branches(node.right)
    return [node]


def _is_language_prefix(shorter: ASTNode, longer: ASTNode) -> bool:
    """Heuristic: can L(shorter) produce a string that is a PROPER prefix of
    some string in L(longer)?

    This approximation catches the most common dangerous cases:
      - shorter is nullable (ε is a prefix of everything)
      - shorter is a literal and longer starts with the same literal
      - shorter is a literal and longer is a concat whose left starts the same
    """
    if _is_nullable(shorter):
        return True                             # ε is prefix of everything
    if isinstance(shorter, LiteralNode):
        if isinstance(longer, LiteralNode):
            return shorter.char == longer.char   # identical single char
        if isinstance(longer, ConcatNode):
            # longer = <head> <tail>; shorter is a prefix iff head starts same
            return _is_language_prefix(shorter, longer.left)
        if isinstance(longer, (StarNode, PlusNode)):
            # (a)+ → shorter 'a' IS a prefix of 'aa', 'aaa', …
            return shorter.char in _first_chars(longer)
    if isinstance(shorter, ConcatNode):
        # Both are concats: check structural prefix
        if isinstance(longer, ConcatNode):
            if not _is_language_prefix(shorter.left, longer.left):
                return False
            return _is_language_prefix(shorter.right, longer.right)
    return False


def _pos(node: ASTNode) -> int | None:
    """Column position of *node* in the original regex (1-indexed), or None."""
    return getattr(node, "position", None)


def _loc(node: ASTNode) -> tuple[int, int] | None:
    p = _pos(node)
    return (p, p) if p is not None else None


# ── Walker ────────────────────────────────────────────────────────────────────

class _SecurityWalker:
    """Post-order AST visitor that collects security findings."""

    def __init__(self) -> None:
        self.findings: list[SecurityFinding] = []
        # Track (rule_id, position) to avoid duplicate findings on same node
        self._emitted: set[tuple[str, int | None]] = set()

    # ── Tree traversal ─────────────────────────────────────────────────────

    def walk(self, node: ASTNode) -> None:
        self._check(node)
        for child in _children(node):
            self.walk(child)

    # ── Dispatcher ─────────────────────────────────────────────────────────

    def _check(self, node: ASTNode) -> None:
        if isinstance(node, (StarNode, PlusNode)):
            self._check_sec001(node)
            self._check_sec002(node)
            self._check_sec003(node)

    def _emit(self, finding: SecurityFinding) -> None:
        key = (finding.rule_id, finding.location[0] if finding.location else None)
        if key not in self._emitted:
            self._emitted.add(key)
            self.findings.append(finding)

    # ── SEC001: Nested Quantifiers ──────────────────────────────────────────

    def _check_sec001(self, outer: StarNode | PlusNode) -> None:
        child = outer.child                        # type: ignore[union-attr]
        if not _subtree_has_star_or_plus(child):
            return
        sym = "*" if isinstance(outer, StarNode) else "+"
        self._emit(SecurityFinding(
            rule_id        = "SEC001",
            risk_level     = HIGH,
            title          = "Nested Quantifiers",
            reason         = (
                f"A '{sym}' quantifier wraps an expression that itself "
                "contains a '*' or '+' repetition."
            ),
            explanation    = (
                "Nested repetition (e.g. '(a+)+', '(a*)*') causes "
                "catastrophic backtracking in backtracking regex engines. "
                "The engine can distribute the same input characters among "
                "inner and outer iterations in exponentially many ways, "
                "hanging on adversarial inputs such as 'aaa...aX'."
            ),
            recommendation = (
                "Eliminate the nesting. '(a+)+' simplifies to 'a+'. "
                "If nesting is intentional, use possessive quantifiers or "
                "atomic groups (if your engine supports them), or use a "
                "DFA-based engine that does not backtrack."
            ),
            location       = _loc(outer),
        ))

    # ── SEC002: Overlapping Alternation in Repetition ──────────────────────

    def _check_sec002(self, outer: StarNode | PlusNode) -> None:
        branches = _collect_union_branches(outer.child)  # type: ignore[union-attr]
        if len(branches) < 2:
            return

        for i in range(len(branches)):
            for j in range(i + 1, len(branches)):
                bi, bj = branches[i], branches[j]
                overlap = _first_chars(bi) & _first_chars(bj)
                if not overlap:
                    continue

                # Severity: HIGH when prefix-language relationship holds
                prefix_rel = (
                    _is_language_prefix(bi, bj)
                    or _is_language_prefix(bj, bi)
                    or _is_nullable(bi)
                    or _is_nullable(bj)
                )
                risk = HIGH if prefix_rel else MEDIUM

                sym = "*" if isinstance(outer, StarNode) else "+"
                sample = sorted(overlap)[:3]
                overlap_repr = ", ".join(repr(c) for c in sample)
                if len(overlap) > 3:
                    overlap_repr += ", …"

                self._emit(SecurityFinding(
                    rule_id        = "SEC002",
                    risk_level     = risk,
                    title          = "Overlapping Alternation in Repetition",
                    reason         = (
                        f"A '{sym}' wraps an alternation whose branches "
                        f"share first characters {{{overlap_repr}}}."
                    ),
                    explanation    = (
                        "When alternation branches can both start from the "
                        "same character and one's language is a prefix of "
                        "another's, a backtracking engine must explore multiple "
                        "ways to split the input across outer iterations, "
                        "potentially creating exponential backtracking "
                        "(e.g. '(a|aa)+' on 'aaaaaX')."
                    ),
                    recommendation = (
                        "Make alternation branches mutually exclusive from "
                        "the first character (e.g. '[ab]' instead of '(a|b)'). "
                        "If overlap is unavoidable, use possessive quantifiers, "
                        "atomic groups, or a DFA-based engine."
                    ),
                    location       = _loc(outer),
                ))
                return   # one SEC002 per outer quantifier is enough

    # ── SEC003: Repetition Over Nullable Expression ─────────────────────────

    def _check_sec003(self, outer: StarNode | PlusNode) -> None:
        child = outer.child                        # type: ignore[union-attr]
        # Skip trivially-ε children and cases already covered by SEC001
        if isinstance(child, EpsilonNode):
            return
        if not _is_nullable(child):
            return
        # If SEC001 already fired for this exact position, don't double-count
        pos = _pos(outer)
        if ("SEC001", pos) in self._emitted:
            return

        sym = "*" if isinstance(outer, StarNode) else "+"
        self._emit(SecurityFinding(
            rule_id        = "SEC003",
            risk_level     = MEDIUM,
            title          = "Repetition Over Nullable Expression",
            reason         = (
                f"A '{sym}' quantifier wraps an expression that can "
                "match the empty string."
            ),
            explanation    = (
                "When the repeated sub-expression can match ε (empty string), "
                "some backtracking engines enter an infinite loop, spinning on "
                "zero-width matches. For example, '(a?)+' on 'X' may iterate "
                "indefinitely before reporting failure."
            ),
            recommendation = (
                "Ensure the repeated sub-expression always consumes at least "
                "one character. For example, rewrite '(a?)+' as 'a*'."
            ),
            location       = _loc(outer),
        ))


# ── Public API ─────────────────────────────────────────────────────────────────

def analyze_security(ast: ASTNode) -> SecurityReport:
    """Walk *ast* and return a :class:`SecurityReport` with all heuristic findings.

    Parameters
    ----------
    ast : ASTNode
        Root of the Abstract Syntax Tree produced by :func:`app.parser.parse_pattern`.

    Returns
    -------
    SecurityReport
        ``overall_risk`` is the highest risk level found, or ``"NONE"`` if the
        pattern is structurally safe according to all implemented rules.
        Every report includes the mandatory DFA-vs-backtracking ``caveat``.

    Notes
    -----
    * Findings are heuristic — see the module-level docstring for known
      false-positive and false-negative cases.
    * The SecureRegex DFA engine itself is immune to ReDoS; findings only
      apply when the same pattern is used in a backtracking engine.
    """
    walker = _SecurityWalker()
    walker.walk(ast)

    findings = tuple(walker.findings)

    if findings:
        overall = max(
            (f.risk_level for f in findings),
            key=lambda r: RISK_ORDER.index(r),
        )
    else:
        overall = NONE

    return SecurityReport(
        findings     = findings,
        overall_risk = overall,
        caveat       = CAVEAT,
    )
