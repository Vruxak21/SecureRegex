"""
Semantic analyser for the SecureRegex AST.

Walk-phase semantic rules
-------------------------

SEM001  ERROR
    Invalid character class range.
    Triggered when ``ClassRange.start > ClassRange.end`` in Unicode codepoint
    order (e.g. ``[z-a]``).  Reported at the column of the start character.

SEM002  WARNING
    Redundant consecutive quantifier.
    Triggered when a quantifier node (Star/Plus/Question) directly wraps
    another quantifier node (e.g. ``a**``, ``b+?``).  The pattern is
    syntactically valid but semantically pointless and often a typo.

SEM003  ERROR
    Unsupported construct: dot wildcard.
    Triggered when a ``DotNode`` is found.  ``.`` is lexed and parsed but is
    outside the v1 supported syntax.  The engine cannot match it.

SEM004  WARNING
    Negated character class.
    Triggered when ``CharClassNode.negate is True``.  Negated classes are
    parsed correctly but the v1 NFA/DFA engine does not implement negation;
    results will be incorrect if this warning is ignored.

See docs/algorithms.md for the full rule reference.

Public API
----------
    analyze(ast: ASTNode) -> list[Diagnostic]
    has_errors(diagnostics: list[Diagnostic]) -> bool
"""

from __future__ import annotations

from app.ast import (
    ASTNode,
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
from app.semantic.diagnostic import Diagnostic, Severity

# ── Convenience aliases ───────────────────────────────────────────────────────

_E = Severity.ERROR
_W = Severity.WARNING

# Node types that represent quantifiers (used for SEM002 detection)
_QUANTIFIER_TYPES = (StarNode, PlusNode, QuestionNode)


# ── Public API ─────────────────────────────────────────────────────────────────

def analyze(ast: ASTNode) -> list[Diagnostic]:
    """Walk *ast* and return all semantic diagnostics (may be empty).

    The returned list is ordered depth-first, left-to-right.  Callers should
    check :func:`has_errors` before continuing the pipeline.

    Parameters
    ----------
    ast : ASTNode
        Root of the AST produced by ``app.parser.parse()``.

    Returns
    -------
    list[Diagnostic]
        Possibly empty list of :class:`Diagnostic` objects.
        Never raises — all findings are returned as diagnostics.
    """
    diags: list[Diagnostic] = []
    _walk(ast, diags)
    return diags


def has_errors(diagnostics: list[Diagnostic]) -> bool:
    """Return True if *diagnostics* contains at least one ERROR-level finding."""
    return any(d.is_error for d in diagnostics)


# ── Recursive walker ──────────────────────────────────────────────────────────

def _walk(node: ASTNode, diags: list[Diagnostic]) -> None:
    """Recursively visit every node in the AST, appending diagnostics."""

    if isinstance(node, LiteralNode) or isinstance(node, EpsilonNode):
        # Leaf nodes — always semantically valid
        return

    if isinstance(node, DotNode):
        _rule_sem003(node, diags)
        return

    if isinstance(node, CharClassNode):
        _rule_sem001(node, diags)
        _rule_sem004(node, diags)
        return      # no children to recurse into for CharClassNode

    if isinstance(node, _QUANTIFIER_TYPES):
        _rule_sem002(node, diags)
        _walk(node.child, diags)
        return

    if isinstance(node, ConcatNode):
        _walk(node.left, diags)
        _walk(node.right, diags)
        return

    if isinstance(node, UnionNode):
        _walk(node.left, diags)
        _walk(node.right, diags)
        return

    # Unknown node type — defensive; should not happen with our AST
    diags.append(Diagnostic(
        severity=_E,
        code="SEM999",
        message=f"Unknown AST node type '{type(node).__name__}' encountered "
                "during semantic analysis.",
        position=None,
    ))


# ── Rule implementations ──────────────────────────────────────────────────────

def _rule_sem001(node: CharClassNode, diags: list[Diagnostic]) -> None:
    """SEM001 — Invalid character class range (start > end)."""
    for r in node.ranges:
        if ord(r.end) < ord(r.start):
            diags.append(Diagnostic(
                severity=_E,
                code="SEM001",
                message=(
                    f"Invalid character class range '{r.start}-{r.end}': "
                    f"start codepoint U+{ord(r.start):04X} "
                    f"is greater than end codepoint U+{ord(r.end):04X}. "
                    "Ranges must be in ascending Unicode order."
                ),
                position=r.start_pos,
            ))


def _rule_sem002(node: ASTNode, diags: list[Diagnostic]) -> None:
    """SEM002 — Redundant consecutive quantifier (e.g. ``a**``)."""
    # node is guaranteed to be a quantifier at this point
    child = node.child  # type: ignore[union-attr]
    if isinstance(child, _QUANTIFIER_TYPES):
        outer = _quantifier_symbol(node)
        inner = _quantifier_symbol(child)
        pos   = getattr(node, "position", None)
        diags.append(Diagnostic(
            severity=_W,
            code="SEM002",
            message=(
                f"Redundant consecutive quantifier '{inner}{outer}': "
                f"'{outer}' directly wraps '{inner}', which is equivalent "
                f"to just '{outer}' in most cases. This is likely a typo."
            ),
            position=pos,
        ))


def _rule_sem003(node: DotNode, diags: list[Diagnostic]) -> None:
    """SEM003 — Unsupported construct: dot wildcard."""
    diags.append(Diagnostic(
        severity=_E,
        code="SEM003",
        message=(
            "The '.' wildcard is not supported in SecureRegex v1. "
            "Use an explicit character class (e.g. [a-zA-Z0-9]) instead."
        ),
        position=node.position,
    ))


def _rule_sem004(node: CharClassNode, diags: list[Diagnostic]) -> None:
    """SEM004 — Negated character class not yet implemented by the v1 engine."""
    if node.negate:
        diags.append(Diagnostic(
            severity=_W,
            code="SEM004",
            message=(
                "Negated character class '[^…]' is parsed but not implemented "
                "by the SecureRegex v1 engine. "
                "The automaton will treat it as a non-negated class; "
                "match results will be incorrect."
            ),
            position=node.position,
        ))


# ── Helpers ───────────────────────────────────────────────────────────────────

def _quantifier_symbol(node: ASTNode) -> str:
    if isinstance(node, StarNode):     return "*"
    if isinstance(node, PlusNode):     return "+"
    if isinstance(node, QuestionNode): return "?"
    return "?"  # unreachable
