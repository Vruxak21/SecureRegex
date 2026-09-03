"""
Hand-written lexer for the SecureRegex regex subset.

Supported syntax (v1)
---------------------
  Literals          any printable character not listed below
  Concatenation     implicit (no explicit operator)
  |                 alternation
  *                 Kleene star (zero-or-more)
  +                 one-or-more
  ?                 zero-or-one
  ( )               grouping
  [ ]               character class
  -                 range operator *inside* [ ]
  ^                 negation *inside* [ ] (lexed; semantic analysis may reject)
  .                 any-character wildcard (lexed; semantic analysis decides)
  \\ x              escape: the next character is treated as a literal

Out of scope (lexed as CHAR or will raise LexerError)
------------------------------------------------------
  Lookahead / lookbehind, backreferences, conditionals, POSIX classes.

Algorithm
---------
A single-pass, one-character-lookahead scanner.  A boolean flag `in_bracket`
tracks whether we are inside a ``[…]`` group so that ``-``, ``^``, and ``]``
receive their special token types only in that context.

Position tracking
-----------------
Columns are 1-indexed.  Line is always 1 (regex patterns are single-line).
The EOF token's column is ``len(pattern) + 1``.

Error handling
--------------
All errors are raised as ``LexerError`` (a ``SecureRegexError`` subclass) with
``position`` (column) and ``char`` set, so the global FastAPI handler can map
them to a structured JSON response without any raw tracebacks.
"""

from __future__ import annotations

from app.config import settings as _default_settings
from app.exceptions import LexerError, RegexTooLongError
from app.lexer.token import Token, TokenType

# ── Constants ─────────────────────────────────────────────────────────────────

# Escape sequences that map to a specific replacement character.
_ESCAPE_MAP: dict[str, str] = {
    "n": "\n",
    "t": "\t",
    "r": "\r",
}

# All characters that are valid after a backslash (metacharacters + common
# named escapes).  Anything *not* in this set is an unrecognised escape.
_ESCAPABLE: frozenset[str] = frozenset(
    r"()|*+?[]\.^$-{}ntr0123456789dwWsSD"
)


# ── Public API ─────────────────────────────────────────────────────────────────

def tokenize(
    pattern: str,
    max_length: int | None = None,
) -> list[Token]:
    """Convert a regex *pattern* string into a flat list of :class:`Token` objects.

    The list **always** ends with a single ``EOF`` token.

    Parameters
    ----------
    pattern    : str        – The raw regex pattern to tokenise.
    max_length : int | None – Override the configured ``max_regex_length`` limit.
                              Pass ``None`` to use the value from ``Settings``.

    Returns
    -------
    list[Token]
        Tokens in source order, terminated by an ``EOF`` token.

    Raises
    ------
    RegexTooLongError
        If ``len(pattern) > max_length``.
    LexerError
        On any invalid character or malformed escape sequence, with ``position``
        and ``char`` attributes set for precise error reporting.
    """

    # ── Length guard ──────────────────────────────────────────────────────
    limit = max_length if max_length is not None else _default_settings.max_regex_length
    if len(pattern) > limit:
        raise RegexTooLongError(
            f"Regex pattern is too long: {len(pattern)} characters "
            f"(maximum allowed is {limit}).",
            detail=(
                f"Shorten the pattern to at most {limit} characters. "
                "You can raise the limit via the SECUREREGEX_MAX_REGEX_LENGTH "
                "environment variable."
            ),
        )

    # ── Scanner state ─────────────────────────────────────────────────────
    tokens:     list[Token] = []
    pos:        int  = 0      # current index into `pattern`
    line:       int  = 1      # always 1; carried for uniform position objects
    in_bracket: bool = False  # True while inside a [...] group

    # ── Main scan loop ────────────────────────────────────────────────────
    while pos < len(pattern):
        ch  = pattern[pos]
        col = pos + 1           # convert to 1-indexed column

        # ── Escape sequences ──────────────────────────────────────────────
        if ch == "\\":
            _check_trailing_backslash(pattern, pos, col)
            next_ch = pattern[pos + 1]
            _check_escape(next_ch, pos + 2, col)     # col of the \, not next_ch
            value = _ESCAPE_MAP.get(next_ch, next_ch)
            tokens.append(Token(TokenType.CHAR, value, line, col))
            pos += 2
            continue

        # ── Invalid control characters ────────────────────────────────────
        _check_control(ch, col)

        # ── Inside character class [...] ──────────────────────────────────
        if in_bracket:
            if ch == "]":
                tokens.append(Token(TokenType.RBRACKET, ch, line, col))
                in_bracket = False
            elif ch == "-":
                tokens.append(Token(TokenType.DASH, ch, line, col))
            elif ch == "^":
                tokens.append(Token(TokenType.CARET, ch, line, col))
            else:
                tokens.append(Token(TokenType.CHAR, ch, line, col))
            pos += 1
            continue

        # ── Outside character class ───────────────────────────────────────
        match ch:
            case "(": tokens.append(Token(TokenType.LPAREN,   ch, line, col))
            case ")": tokens.append(Token(TokenType.RPAREN,   ch, line, col))
            case "|": tokens.append(Token(TokenType.OR,       ch, line, col))
            case "*": tokens.append(Token(TokenType.STAR,     ch, line, col))
            case "+": tokens.append(Token(TokenType.PLUS,     ch, line, col))
            case "?": tokens.append(Token(TokenType.QUESTION, ch, line, col))
            case ".": tokens.append(Token(TokenType.DOT,      ch, line, col))
            case "[":
                tokens.append(Token(TokenType.LBRACKET, ch, line, col))
                in_bracket = True
            case _:
                # Everything else (letters, digits, punctuation, -,  ], ^
                # *outside* brackets, unicode…) is a plain literal character.
                tokens.append(Token(TokenType.CHAR, ch, line, col))

        pos += 1

    # ── Sentinel EOF ──────────────────────────────────────────────────────
    tokens.append(Token(TokenType.EOF, "", line, len(pattern) + 1))
    return tokens


# ── Internal helpers ──────────────────────────────────────────────────────────

def _check_trailing_backslash(pattern: str, pos: int, col: int) -> None:
    """Raise ``LexerError`` if the backslash at *pos* has no following char."""
    if pos + 1 >= len(pattern):
        raise LexerError(
            f"Trailing backslash at column {col}: "
            "a backslash must be followed by a character to escape.",
            position=col,
            char="\\",
            detail=(
                "Place a second backslash (\\\\) to match a literal backslash, "
                "or escape any metacharacter."
            ),
        )


def _check_escape(ch: str, _: int, col: int) -> None:
    """Raise ``LexerError`` for an unrecognised escape sequence.

    We allow all metacharacters, named escapes (n/t/r), and the digit/word/space
    class shorthand letters (d/w/s) even though the engine doesn't yet implement
    them — the semantic analyser will reject unsupported ones later.
    """
    if ch not in _ESCAPABLE:
        raise LexerError(
            f"Unrecognised escape sequence '\\{ch}' at column {col}.",
            position=col,
            char=f"\\{ch}",
            detail=(
                f"The character '{ch}' cannot follow a backslash in this "
                "regex dialect.  Did you mean to escape a metacharacter such "
                r"as \( \) \| \* \+ \? \[ \] \\ \. ?"
            ),
        )


def _check_control(ch: str, col: int) -> None:
    """Raise ``LexerError`` for non-printable control characters."""
    cp = ord(ch)
    if cp < 0x20 and ch not in "\t\n\r":
        raise LexerError(
            f"Invalid control character (U+{cp:04X}) at column {col}.",
            position=col,
            char=ch,
            detail=(
                f"The character with codepoint {cp} is not valid inside a "
                "regex pattern.  Use an escape sequence (e.g. \\t for tab) "
                "to match control characters."
            ),
        )
