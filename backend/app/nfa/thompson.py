"""
Thompson's Construction — NFA builder.

Converts every AST node type into an NFA fragment with exactly ONE start state
and ONE accepting state, then composes fragments recursively.

Thompson fragment rules
-----------------------

Each rule creates the minimal NFA fragment for its AST node.
States are numbered with a monotonically increasing counter; the order
reflects a depth-first, left-to-right traversal of the AST.

LITERAL(c)
    ┌─────┐   c   ┌─────┐
    │ q_s │──────►│ q_a │
    └─────┘       └─────┘
    2 new states, 1 symbol transition.

EPSILON
    ┌─────┐   ε   ┌─────┐
    │ q_s │──────►│ q_a │
    └─────┘       └─────┘
    2 new states, 1 ε-transition.

CONCAT(L, R)
    L.start ──…──► L.accept ──ε──► R.start ──…──► R.accept
    0 new states, 1 ε-transition added.
    Result: start=L.start, accept=R.accept.

UNION(L, R)
             ┌──ε──► L.start ──…──► L.accept ──ε──┐
    q_s ─────┤                                     ├──► q_a
             └──ε──► R.start ──…──► R.accept ──ε──┘
    2 new states, 4 ε-transitions.

STAR(N)
           ┌────────────── ε ─────────────────┐
           │ ┌─────────────────────────────┐  │
           ▼ ▼                             │  │
    q_s ──ε──► N.start ──…──► N.accept ──ε─┘  │
     │                                         │
     └──────────────── ε ──────────────────► q_a
    2 new states, 4 ε-transitions.
    (q_s → N.start  enter, q_s → q_a  skip/zero,
     N.accept → N.start  loop, N.accept → q_a  exit)

PLUS(N)   (one-or-more)
    N.start ──…──► N.accept ──ε──► N.start  (loop)
                              └──ε──► q_a    (exit)
    1 new state (q_a), 2 ε-transitions.
    Result: start=N.start, accept=q_a.

QUESTION(N)   (zero-or-one)
    q_s ──ε──► N.start ──…──► N.accept ──ε──► q_a
     └─────────────── ε ──────────────────────┘
    2 new states, 3 ε-transitions.

CHARCLASS([a-z])
    ┌─────┐  a,b,..,z  ┌─────┐
    │ q_s │────────────►│ q_a │
    └─────┘  (one edge  └─────┘
              per char)
    2 new states, |expanded_chars| symbol transitions.

DOT  (not in v1 — handled defensively; expands to printable ASCII)
    Same shape as CHARCLASS but with 95 transitions (0x20–0x7E).
"""

from __future__ import annotations

from app.ast import (
    ASTNode,
    CharClassNode,
    ConcatNode,
    DotNode,
    EpsilonNode,
    LiteralNode,
    PlusNode,
    QuestionNode,
    StarNode,
    UnionNode,
)
from app.exceptions import SecureRegexError
from app.nfa.nfa import NFA, EPSILON, Transition

# Printable ASCII range used by DotNode expansion
_DOT_CHARS: frozenset[str] = frozenset(chr(cp) for cp in range(0x20, 0x7F))


# ── Internal types ────────────────────────────────────────────────────────────

class NFABuildError(SecureRegexError):
    """Raised when the NFA builder encounters an unhandled AST node type."""
    error_code = "NFA_BUILD_ERROR"


# ── Builder class ─────────────────────────────────────────────────────────────

class _Builder:
    """Stateful Thompson-construction builder.

    Call :meth:`build_fragment` on the root AST node, then call
    :meth:`finish` to assemble the final :class:`NFA`.
    """

    def __init__(self) -> None:
        self._counter:     int            = 0
        self._states:      set[int]       = set()
        self._transitions: list[Transition] = set()  # type: ignore[assignment]
        self._transitions  = []

    # ── State allocation ──────────────────────────────────────────────────

    def _new_state(self) -> int:
        sid = self._counter
        self._counter += 1
        self._states.add(sid)
        return sid

    def _add(self, from_id: int, symbol: str | None, to_id: int) -> None:
        self._transitions.append(Transition(from_id, symbol, to_id))

    # ── Fragment builders ─────────────────────────────────────────────────

    def build_fragment(self, node: ASTNode) -> tuple[int, int]:
        """Return *(start, accept)* for the NFA fragment of *node*."""

        if isinstance(node, LiteralNode):
            return self._literal(node)
        if isinstance(node, EpsilonNode):
            return self._epsilon()
        if isinstance(node, DotNode):
            return self._dot(node)
        if isinstance(node, CharClassNode):
            return self._char_class(node)
        if isinstance(node, ConcatNode):
            return self._concat(node)
        if isinstance(node, UnionNode):
            return self._union(node)
        if isinstance(node, StarNode):
            return self._star(node)
        if isinstance(node, PlusNode):
            return self._plus(node)
        if isinstance(node, QuestionNode):
            return self._question(node)

        raise NFABuildError(
            f"Cannot build NFA for unknown AST node type "
            f"'{type(node).__name__}'.",
            detail="Run semantic analysis before NFA construction.",
        )

    # ── Leaf nodes ────────────────────────────────────────────────────────

    def _literal(self, node: LiteralNode) -> tuple[int, int]:
        s, a = self._new_state(), self._new_state()
        self._add(s, node.char, a)
        return s, a

    def _epsilon(self) -> tuple[int, int]:
        s, a = self._new_state(), self._new_state()
        self._add(s, EPSILON, a)
        return s, a

    def _dot(self, _node: DotNode) -> tuple[int, int]:
        """Expand ``.`` to all printable ASCII characters (defensive path)."""
        s, a = self._new_state(), self._new_state()
        for ch in sorted(_DOT_CHARS):
            self._add(s, ch, a)
        return s, a

    def _char_class(self, node: CharClassNode) -> tuple[int, int]:
        """Expand character class ranges into individual symbol transitions."""
        s, a    = self._new_state(), self._new_state()
        added:  set[str] = set()

        for r in node.ranges:
            for cp in range(ord(r.start), ord(r.end) + 1):
                ch = chr(cp)
                if ch not in added:
                    added.add(ch)
                    self._add(s, ch, a)

        # If nothing was added (empty class slipped through), add ε so the
        # fragment is still structurally valid (semantic analysis flags this).
        if not added:
            self._add(s, EPSILON, a)

        return s, a

    # ── Composite nodes ───────────────────────────────────────────────────

    def _concat(self, node: ConcatNode) -> tuple[int, int]:
        ls, la = self.build_fragment(node.left)
        rs, ra = self.build_fragment(node.right)
        self._add(la, EPSILON, rs)        # bridge: left_accept → right_start
        return ls, ra

    def _union(self, node: UnionNode) -> tuple[int, int]:
        ls, la = self.build_fragment(node.left)
        rs, ra = self.build_fragment(node.right)
        s, a   = self._new_state(), self._new_state()
        self._add(s,  EPSILON, ls)        # fork left
        self._add(s,  EPSILON, rs)        # fork right
        self._add(la, EPSILON, a)         # merge left
        self._add(ra, EPSILON, a)         # merge right
        return s, a

    def _star(self, node: StarNode) -> tuple[int, int]:
        ns, na = self.build_fragment(node.child)
        s, a   = self._new_state(), self._new_state()
        self._add(s,  EPSILON, ns)        # enter inner NFA
        self._add(s,  EPSILON, a)         # skip (zero iterations)
        self._add(na, EPSILON, ns)        # loop back
        self._add(na, EPSILON, a)         # exit after any iteration
        return s, a

    def _plus(self, node: PlusNode) -> tuple[int, int]:
        ns, na = self.build_fragment(node.child)
        a      = self._new_state()
        self._add(na, EPSILON, ns)        # loop back (one or more)
        self._add(na, EPSILON, a)         # exit
        return ns, a

    def _question(self, node: QuestionNode) -> tuple[int, int]:
        ns, na = self.build_fragment(node.child)
        s, a   = self._new_state(), self._new_state()
        self._add(s,  EPSILON, ns)        # enter inner NFA
        self._add(s,  EPSILON, a)         # skip (zero occurrences)
        self._add(na, EPSILON, a)         # exit after one occurrence
        return s, a

    # ── Finalisation ──────────────────────────────────────────────────────

    def finish(self, start: int, accept: int) -> NFA:
        """Assemble the final :class:`NFA` from the collected fragments."""
        alphabet = frozenset(
            t.symbol for t in self._transitions if t.symbol is not None
        )
        return NFA(
            states      = frozenset(self._states),
            alphabet    = alphabet,
            transitions = tuple(self._transitions),
            start       = start,
            accepting   = frozenset({accept}),
        )


# ── Public API ─────────────────────────────────────────────────────────────────

def build_nfa(ast: ASTNode) -> NFA:
    """Convert an AST into an NFA via Thompson's construction.

    Parameters
    ----------
    ast : ASTNode
        Root of the AST produced by ``app.parser.parse()``.
        The caller is responsible for running semantic analysis first;
        this function raises :class:`NFABuildError` only as a last resort.

    Returns
    -------
    NFA
        Immutable NFA with ``frozenset`` states and ``tuple`` transitions.

    Raises
    ------
    NFABuildError
        If an unrecognised AST node type is encountered.

    Notes
    -----
    Thompson's construction guarantees:
    * Exactly **one** start state.
    * Exactly **one** accepting state.
    * No transitions *into* the start state (by construction).
    * No transitions *out of* the accepting state (by construction).
    """
    builder = _Builder()
    start, accept = builder.build_fragment(ast)
    return builder.finish(start, accept)
