"""
Token definitions for the SecureRegex lexer.

Design notes
------------
* ``TokenType`` is an enum so pattern-matching (match/case) and set-membership
  checks are O(1) and IDE-friendly.
* ``Token`` is a frozen dataclass — tokens are immutable value objects.
  Frozen dataclasses give us ``__hash__`` for free (useful in sets/dicts later).
* Line is always 1 (regex patterns are single-line), but we carry it anyway so
  the position format is uniform across the whole compiler.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class TokenType(Enum):
    """Every distinct lexical category the lexer can produce.

    Categories
    ----------
    Structural operators (outside ``[…]``)
        LPAREN, RPAREN, OR, STAR, PLUS, QUESTION

    Character class delimiters
        LBRACKET, RBRACKET, DASH, CARET

    Literal / wildcard
        CHAR    – any literal character (including escaped metacharacters)
        DOT     – the ``.`` wildcard (lexed but semantic analysis may reject it)

    Sentinel
        EOF     – always the last token; value is the empty string ``""``
    """

    # ── Structural ─────────────────────────────────────────────────────────
    LPAREN   = "LPAREN"    # (
    RPAREN   = "RPAREN"    # )
    OR       = "OR"        # |
    STAR     = "STAR"      # *
    PLUS     = "PLUS"      # +
    QUESTION = "QUESTION"  # ?

    # ── Character classes ──────────────────────────────────────────────────
    LBRACKET = "LBRACKET"  # [  (opens a character class)
    RBRACKET = "RBRACKET"  # ]  (closes a character class)
    DASH     = "DASH"      # -  (range operator inside [...])
    CARET    = "CARET"     # ^  (negation inside [...])

    # ── Literal / wildcard ─────────────────────────────────────────────────
    CHAR = "CHAR"          # any literal character or resolved escape sequence
    DOT  = "DOT"           # . (any-character wildcard — lexed for completeness)

    # ── Sentinel ───────────────────────────────────────────────────────────
    EOF = "EOF"            # end of token stream; value == ""


@dataclass(frozen=True)
class Token:
    """A single lexical token.

    Attributes
    ----------
    type   : TokenType   – the category of this token
    value  : str         – the raw character(s) this token represents
    line   : int         – source line (always 1; kept for uniform position format)
    column : int         – 1-indexed column of the *first* character of this token
    """

    type:   TokenType
    value:  str
    line:   int
    column: int

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"Token({self.type.name!s:<10} value={self.value!r:<6} "
            f"line={self.line} col={self.column})"
        )
