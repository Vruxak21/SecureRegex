"""
AST node definitions for the SecureRegex compiler.

Design principles
-----------------
* Every node is a frozen dataclass — immutable value objects, hashable,
  comparable with ``==`` out of the box (essential for test assertions).
* The ``ASTNode`` ABC enforces that every concrete node implements
  ``to_dict()`` for JSON serialisation and frontend tree visualisation.
* ``ClassRange`` is a separate dataclass so the char-class node's ranges
  list is typed and serialisable independently.
* ``EpsilonNode`` is included in the hierarchy because the NFA builder
  (Phase 4) needs to represent ε-transitions explicitly.  The parser
  itself never generates ``EpsilonNode`` directly; it raises a
  ``ParseError`` instead (e.g. for empty groups).

Node hierarchy
--------------
ASTNode (ABC)
├── LiteralNode  – single character literal
├── DotNode      – the ``.`` wildcard (any character)
├── EpsilonNode  – empty string ε  (used by NFA builder)
├── ConcatNode   – concatenation (binary, left-associative)
├── UnionNode    – alternation  |  (binary, left-associative)
├── StarNode     – Kleene star  *
├── PlusNode     – one-or-more  +
├── QuestionNode – zero-or-one  ?
└── CharClassNode – character class  [a-z]  with optional negation
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


# ── Abstract base ──────────────────────────────────────────────────────────────

class ASTNode(ABC):
    """Base class for every node in the regex Abstract Syntax Tree."""

    @abstractmethod
    def to_dict(self) -> dict:
        """Return a JSON-serialisable ``dict`` representing this subtree.

        The ``"type"`` key always holds the node's class name without the
        ``Node`` suffix, so frontends can switch on it.
        """

    def __repr__(self) -> str:  # pragma: no cover
        return f"{self.__class__.__name__}()"


# ── Leaf nodes ─────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class LiteralNode(ASTNode):
    """A single literal character, e.g. ``a`` or ``\\*`` (escaped metachar)."""

    char: str  # exactly one Unicode character (or resolved escape value)

    def to_dict(self) -> dict:
        return {"type": "Literal", "char": self.char}

    def __repr__(self) -> str:  # pragma: no cover
        return f"LiteralNode({self.char!r})"


@dataclass(frozen=True)
class DotNode(ASTNode):
    """The ``.`` wildcard — matches any single character.

    Flagged as SEM003 by the semantic analyser (not in v1 supported syntax).
    """

    position: int | None = field(default=None, compare=False)

    def to_dict(self) -> dict:
        return {"type": "Dot"}


@dataclass(frozen=True)
class EpsilonNode(ASTNode):
    """The empty string ε — matches without consuming any input.

    Not produced by the parser (empty groups are errors); used by the
    NFA builder to represent Thompson ε-transitions.
    """

    def to_dict(self) -> dict:
        return {"type": "Epsilon"}


# ── Character class ────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ClassRange:
    """A single character or character range inside ``[…]``.

    A single character ``'a'`` is stored as ``ClassRange(start='a', end='a')``.
    A range ``'a'-'z'`` is stored as ``ClassRange(start='a', end='z')``.

    ``start_pos`` carries the 1-indexed column of the *start* character in the
    original source (for precise SEM001 error reporting).  It is excluded from
    ``__eq__`` and ``__hash__`` so that test assertions can compare ranges by
    value without caring about source location.
    """

    start:     str
    end:       str
    start_pos: int | None = field(default=None, compare=False)

    def to_dict(self) -> dict:
        return {"start": self.start, "end": self.end}

    def __repr__(self) -> str:  # pragma: no cover
        if self.start == self.end:
            return f"ClassRange({self.start!r})"
        return f"ClassRange({self.start!r}-{self.end!r})"


@dataclass(frozen=True)
class CharClassNode(ASTNode):
    """A character class ``[…]`` or negated class ``[^…]``.

    Attributes
    ----------
    negate   : bool                  – True when the class is negated ``[^…]``.
    ranges   : tuple[ClassRange, …]  – Ranges/single-chars inside the brackets.
    position : int | None            – Column of the opening ``[`` (compare=False).
    """

    negate:   bool
    ranges:   tuple[ClassRange, ...]
    position: int | None = field(default=None, compare=False)

    def to_dict(self) -> dict:
        return {
            "type":   "CharClass",
            "negate": self.negate,
            "ranges": [r.to_dict() for r in self.ranges],
        }

    def __repr__(self) -> str:  # pragma: no cover
        neg = "^" if self.negate else ""
        inner = "".join(
            f"{r.start}" if r.start == r.end else f"{r.start}-{r.end}"
            for r in self.ranges
        )
        return f"CharClassNode([{neg}{inner}])"


# ── Unary nodes (quantifiers) ──────────────────────────────────────────────────

@dataclass(frozen=True)
class StarNode(ASTNode):
    """Kleene star ``*`` — zero or more repetitions."""

    child:    ASTNode
    position: int | None = field(default=None, compare=False)

    def to_dict(self) -> dict:
        return {"type": "Star", "child": self.child.to_dict()}

    def __repr__(self) -> str:  # pragma: no cover
        return f"StarNode({self.child!r})"


@dataclass(frozen=True)
class PlusNode(ASTNode):
    """One-or-more ``+``."""

    child:    ASTNode
    position: int | None = field(default=None, compare=False)

    def to_dict(self) -> dict:
        return {"type": "Plus", "child": self.child.to_dict()}

    def __repr__(self) -> str:  # pragma: no cover
        return f"PlusNode({self.child!r})"


@dataclass(frozen=True)
class QuestionNode(ASTNode):
    """Zero-or-one ``?``."""

    child:    ASTNode
    position: int | None = field(default=None, compare=False)

    def to_dict(self) -> dict:
        return {"type": "Question", "child": self.child.to_dict()}

    def __repr__(self) -> str:  # pragma: no cover
        return f"QuestionNode({self.child!r})"


# ── Binary nodes ───────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ConcatNode(ASTNode):
    """Concatenation of two sub-expressions (left-associative).

    ``abc`` → ``Concat(Concat(a, b), c)``
    """

    left:  ASTNode
    right: ASTNode

    def to_dict(self) -> dict:
        return {
            "type":  "Concat",
            "left":  self.left.to_dict(),
            "right": self.right.to_dict(),
        }

    def __repr__(self) -> str:  # pragma: no cover
        return f"ConcatNode({self.left!r}, {self.right!r})"


@dataclass(frozen=True)
class UnionNode(ASTNode):
    """Alternation ``|`` between two sub-expressions (left-associative).

    ``a|b|c`` → ``Union(Union(a, b), c)``
    """

    left:  ASTNode
    right: ASTNode

    def to_dict(self) -> dict:
        return {
            "type":  "Union",
            "left":  self.left.to_dict(),
            "right": self.right.to_dict(),
        }

    def __repr__(self) -> str:  # pragma: no cover
        return f"UnionNode({self.left!r}, {self.right!r})"
