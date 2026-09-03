"""
Phase 1 — Lexer tests.

Coverage targets
----------------
1.  Canonical pattern ``(a|b)*abb`` — exact token stream
2.  Character classes  ``[a-z]`` — DASH emitted only inside [...]
3.  Quantifiers: ``*``, ``+``, ``?``
4.  Nested / complex: ``(ab)+|[0-9]*``
5.  Escaped metacharacters  ``\\(`` ``\\*`` ``\\\\``
6.  Named escapes  ``\\n`` ``\\t`` ``\\r``
7.  DOT (wildcard) token
8.  ``^`` (CARET) inside a bracket class
9.  ``-`` outside brackets → CHAR, not DASH
10. ``]`` outside brackets → CHAR, not RBRACKET
11. Empty input → only EOF
12. Single character input
13. Max-length rejection → RegexTooLongError
14. Invalid control character → LexerError with correct position
15. Trailing backslash → LexerError
16. Unrecognised escape sequence → LexerError
17. LexerError carries position dict and char field
18. EOF is always the last token (all inputs)
19. Column positions are 1-indexed and contiguous
20. Unicode literals (e.g. ``é``) are accepted as CHAR
"""

from __future__ import annotations

import pytest

from app.lexer import Token, TokenType, tokenize
from app.exceptions import LexerError, RegexTooLongError


# ── Helpers ───────────────────────────────────────────────────────────────────

def types(tokens: list[Token]) -> list[TokenType]:
    """Extract just the TokenType list (for compact assertions)."""
    return [t.type for t in tokens]


def values(tokens: list[Token]) -> list[str]:
    """Extract just the value list."""
    return [t.value for t in tokens]


# ─────────────────────────────────────────────────────────────────────────────
# 1. Canonical pattern  (a|b)*abb
# ─────────────────────────────────────────────────────────────────────────────

class TestCanonicalPattern:
    """Full exact-match test for ``(a|b)*abb``."""

    PATTERN = "(a|b)*abb"

    @pytest.fixture
    def tokens(self) -> list[Token]:
        return tokenize(self.PATTERN)

    def test_token_count(self, tokens):
        # 9 source chars + 1 EOF = 10 tokens
        assert len(tokens) == 10

    def test_exact_types(self, tokens):
        assert types(tokens) == [
            TokenType.LPAREN,
            TokenType.CHAR,
            TokenType.OR,
            TokenType.CHAR,
            TokenType.RPAREN,
            TokenType.STAR,
            TokenType.CHAR,
            TokenType.CHAR,
            TokenType.CHAR,
            TokenType.EOF,
        ]

    def test_exact_values(self, tokens):
        assert values(tokens) == ["(", "a", "|", "b", ")", "*", "a", "b", "b", ""]

    def test_column_positions(self, tokens):
        """Columns are 1-indexed and match character positions exactly."""
        expected_cols = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        assert [t.column for t in tokens] == expected_cols

    def test_all_lines_are_one(self, tokens):
        assert all(t.line == 1 for t in tokens)

    def test_eof_value_is_empty_string(self, tokens):
        assert tokens[-1].value == ""

    def test_eof_type(self, tokens):
        assert tokens[-1].type is TokenType.EOF


# ─────────────────────────────────────────────────────────────────────────────
# 2. Character class  [a-z]
# ─────────────────────────────────────────────────────────────────────────────

class TestCharacterClass:

    def test_types_for_a_to_z(self):
        tokens = tokenize("[a-z]")
        assert types(tokens) == [
            TokenType.LBRACKET,
            TokenType.CHAR,
            TokenType.DASH,
            TokenType.CHAR,
            TokenType.RBRACKET,
            TokenType.EOF,
        ]

    def test_values_for_a_to_z(self):
        tokens = tokenize("[a-z]")
        assert values(tokens) == ["[", "a", "-", "z", "]", ""]

    def test_columns_for_a_to_z(self):
        tokens = tokenize("[a-z]")
        assert [t.column for t in tokens] == [1, 2, 3, 4, 5, 6]

    def test_multi_char_class(self):
        """``[abc]`` has no DASH — three CHAR tokens between brackets."""
        tokens = tokenize("[abc]")
        assert types(tokens) == [
            TokenType.LBRACKET,
            TokenType.CHAR,
            TokenType.CHAR,
            TokenType.CHAR,
            TokenType.RBRACKET,
            TokenType.EOF,
        ]

    def test_digit_range(self):
        tokens = tokenize("[0-9]")
        inner = [t for t in tokens if t.type not in {TokenType.LBRACKET, TokenType.RBRACKET, TokenType.EOF}]
        assert inner[0].type is TokenType.CHAR and inner[0].value == "0"
        assert inner[1].type is TokenType.DASH
        assert inner[2].type is TokenType.CHAR and inner[2].value == "9"

    def test_caret_inside_bracket(self):
        """``^`` immediately after ``[`` produces CARET token."""
        tokens = tokenize("[^a-z]")
        assert tokens[1].type is TokenType.CARET
        assert tokens[1].value == "^"

    def test_dash_outside_bracket_is_char(self):
        """`-` outside ``[…]`` must become CHAR, not DASH."""
        tokens = tokenize("a-b")
        dash_tok = tokens[1]
        assert dash_tok.type is TokenType.CHAR
        assert dash_tok.value == "-"

    def test_rbracket_outside_bracket_is_char(self):
        """`]` outside any bracket context is a plain literal CHAR."""
        tokens = tokenize("a]b")
        assert tokens[1].type is TokenType.CHAR
        assert tokens[1].value == "]"


# ─────────────────────────────────────────────────────────────────────────────
# 3. Quantifiers
# ─────────────────────────────────────────────────────────────────────────────

class TestQuantifiers:

    def test_star(self):
        assert types(tokenize("a*")) == [TokenType.CHAR, TokenType.STAR, TokenType.EOF]

    def test_plus(self):
        assert types(tokenize("a+")) == [TokenType.CHAR, TokenType.PLUS, TokenType.EOF]

    def test_question(self):
        assert types(tokenize("a?")) == [TokenType.CHAR, TokenType.QUESTION, TokenType.EOF]

    def test_mixed_quantifiers(self):
        tokens = tokenize("a*b+c?")
        assert types(tokens) == [
            TokenType.CHAR, TokenType.STAR,
            TokenType.CHAR, TokenType.PLUS,
            TokenType.CHAR, TokenType.QUESTION,
            TokenType.EOF,
        ]


# ─────────────────────────────────────────────────────────────────────────────
# 4. Complex patterns
# ─────────────────────────────────────────────────────────────────────────────

class TestComplexPatterns:

    def test_group_plus_alternation_class(self):
        """``(ab)+|[0-9]*`` exercises most token types together."""
        tokens = tokenize("(ab)+|[0-9]*")
        expected = [
            TokenType.LPAREN,
            TokenType.CHAR,   # a
            TokenType.CHAR,   # b
            TokenType.RPAREN,
            TokenType.PLUS,
            TokenType.OR,
            TokenType.LBRACKET,
            TokenType.CHAR,   # 0
            TokenType.DASH,
            TokenType.CHAR,   # 9
            TokenType.RBRACKET,
            TokenType.STAR,
            TokenType.EOF,
        ]
        assert types(tokens) == expected

    def test_nested_groups(self):
        tokens = tokenize("((a|b))")
        assert tokens[0].type is TokenType.LPAREN
        assert tokens[1].type is TokenType.LPAREN
        assert tokens[-2].type is TokenType.RPAREN
        assert tokens[-3].type is TokenType.RPAREN

    def test_multiple_char_classes(self):
        tokens = tokenize("[a-z][0-9]")
        bracket_types = [t.type for t in tokens if t.type in {TokenType.LBRACKET, TokenType.RBRACKET}]
        assert bracket_types == [TokenType.LBRACKET, TokenType.RBRACKET, TokenType.LBRACKET, TokenType.RBRACKET]


# ─────────────────────────────────────────────────────────────────────────────
# 5 & 6. Escape sequences
# ─────────────────────────────────────────────────────────────────────────────

class TestEscapeSequences:

    def test_escaped_lparen(self):
        tokens = tokenize(r"\(")
        assert tokens[0].type is TokenType.CHAR
        assert tokens[0].value == "("

    def test_escaped_star(self):
        tokens = tokenize(r"\*")
        assert tokens[0].type is TokenType.CHAR
        assert tokens[0].value == "*"

    def test_escaped_backslash(self):
        tokens = tokenize(r"\\")
        assert tokens[0].type is TokenType.CHAR
        assert tokens[0].value == "\\"

    def test_escaped_pipe(self):
        tokens = tokenize(r"\|")
        assert tokens[0].type is TokenType.CHAR
        assert tokens[0].value == "|"

    def test_named_escape_newline(self):
        tokens = tokenize(r"\n")
        assert tokens[0].type is TokenType.CHAR
        assert tokens[0].value == "\n"

    def test_named_escape_tab(self):
        tokens = tokenize(r"\t")
        assert tokens[0].type is TokenType.CHAR
        assert tokens[0].value == "\t"

    def test_named_escape_carriage_return(self):
        tokens = tokenize(r"\r")
        assert tokens[0].type is TokenType.CHAR
        assert tokens[0].value == "\r"

    def test_escape_occupies_single_token(self):
        """An escape sequence ``\\(`` is ONE token with col pointing at the backslash."""
        tokens = tokenize(r"a\(b")
        assert len(tokens) == 4  # a, \(, b, EOF
        assert tokens[1].type is TokenType.CHAR
        assert tokens[1].value == "("
        assert tokens[1].column == 2   # backslash is at col 2

    def test_escaped_dot(self):
        tokens = tokenize(r"\.")
        assert tokens[0].type is TokenType.CHAR
        assert tokens[0].value == "."


# ─────────────────────────────────────────────────────────────────────────────
# 7. DOT wildcard
# ─────────────────────────────────────────────────────────────────────────────

class TestDot:

    def test_dot_produces_dot_token(self):
        tokens = tokenize("a.b")
        assert tokens[1].type is TokenType.DOT
        assert tokens[1].value == "."

    def test_dot_column(self):
        tokens = tokenize("a.b")
        assert tokens[1].column == 2


# ─────────────────────────────────────────────────────────────────────────────
# 8 & 9 & 10 — already in TestCharacterClass above
# ─────────────────────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────────────────
# 11. Empty input
# ─────────────────────────────────────────────────────────────────────────────

class TestEmptyInput:

    def test_empty_returns_single_eof(self):
        tokens = tokenize("")
        assert len(tokens) == 1
        assert tokens[0].type is TokenType.EOF

    def test_empty_eof_column_is_one(self):
        tokens = tokenize("")
        assert tokens[0].column == 1

    def test_empty_eof_value_is_empty_string(self):
        tokens = tokenize("")
        assert tokens[0].value == ""


# ─────────────────────────────────────────────────────────────────────────────
# 12. Single character
# ─────────────────────────────────────────────────────────────────────────────

class TestSingleCharacter:

    def test_single_letter(self):
        tokens = tokenize("x")
        assert types(tokens) == [TokenType.CHAR, TokenType.EOF]
        assert tokens[0].value == "x"
        assert tokens[0].column == 1

    def test_single_metachar(self):
        tokens = tokenize("*")
        assert tokens[0].type is TokenType.STAR


# ─────────────────────────────────────────────────────────────────────────────
# 13. Max-length rejection
# ─────────────────────────────────────────────────────────────────────────────

class TestMaxLength:

    def test_exactly_at_limit_is_ok(self):
        pattern = "a" * 10
        tokens = tokenize(pattern, max_length=10)
        assert tokens[-1].type is TokenType.EOF

    def test_one_over_limit_raises(self):
        pattern = "a" * 11
        with pytest.raises(RegexTooLongError) as exc_info:
            tokenize(pattern, max_length=10)
        err = exc_info.value
        assert err.status_code == 422
        assert err.error_code == "REGEX_TOO_LONG"

    def test_error_message_contains_lengths(self):
        pattern = "a" * 11
        with pytest.raises(RegexTooLongError) as exc_info:
            tokenize(pattern, max_length=10)
        assert "11" in exc_info.value.message
        assert "10" in exc_info.value.message

    def test_empty_string_never_too_long(self):
        tokens = tokenize("", max_length=0)
        # len("") == 0 which is NOT > 0, so it passes
        assert tokens[0].type is TokenType.EOF

    def test_uses_settings_default_when_no_override(self):
        """Without an explicit max_length the global Settings.max_regex_length applies."""
        from app.config import settings
        # A pattern shorter than the default (1000) must succeed
        tokens = tokenize("abc")
        assert tokens[-1].type is TokenType.EOF
        # A pattern longer than the default must fail
        with pytest.raises(RegexTooLongError):
            tokenize("a" * (settings.max_regex_length + 1))


# ─────────────────────────────────────────────────────────────────────────────
# 14. Invalid control character
# ─────────────────────────────────────────────────────────────────────────────

class TestInvalidControlCharacter:

    def test_null_byte_raises(self):
        with pytest.raises(LexerError) as exc_info:
            tokenize("a\x00b")
        err = exc_info.value
        assert err.error_code == "LEXER_ERROR"

    def test_null_byte_position(self):
        with pytest.raises(LexerError) as exc_info:
            tokenize("a\x00b")
        # \x00 is at index 1 → column 2
        assert exc_info.value.position == 2

    def test_null_byte_char_field(self):
        with pytest.raises(LexerError) as exc_info:
            tokenize("a\x00b")
        assert exc_info.value.char == "\x00"

    def test_bell_char_raises(self):
        with pytest.raises(LexerError):
            tokenize("\x07")

    def test_tab_is_allowed(self):
        """\\t (0x09) is valid as a literal char — must NOT raise."""
        tokens = tokenize("a\tb")
        assert tokens[1].type is TokenType.CHAR
        assert tokens[1].value == "\t"

    def test_control_char_at_start(self):
        with pytest.raises(LexerError) as exc_info:
            tokenize("\x01abc")
        assert exc_info.value.position == 1

    def test_control_char_at_end(self):
        with pytest.raises(LexerError) as exc_info:
            tokenize("abc\x05")
        assert exc_info.value.position == 4

    def test_to_dict_has_position_and_char(self):
        with pytest.raises(LexerError) as exc_info:
            tokenize("a\x00b")
        d = exc_info.value.to_dict()
        assert "position" in d
        assert d["position"]["line"] == 1
        assert d["position"]["column"] == 2
        assert "char" in d


# ─────────────────────────────────────────────────────────────────────────────
# 15. Trailing backslash
# ─────────────────────────────────────────────────────────────────────────────

class TestTrailingBackslash:

    def test_lone_backslash_raises(self):
        with pytest.raises(LexerError) as exc_info:
            tokenize("\\")
        assert "backslash" in exc_info.value.message.lower()

    def test_trailing_backslash_position(self):
        with pytest.raises(LexerError) as exc_info:
            tokenize("ab\\")
        # backslash is at index 2 → column 3
        assert exc_info.value.position == 3

    def test_trailing_backslash_char_field(self):
        with pytest.raises(LexerError) as exc_info:
            tokenize("\\")
        assert exc_info.value.char == "\\"


# ─────────────────────────────────────────────────────────────────────────────
# 16. Unrecognised escape sequence
# ─────────────────────────────────────────────────────────────────────────────

class TestUnrecognisedEscape:

    def test_backslash_k_raises(self):
        """``\\k`` is not a valid escape in our dialect."""
        with pytest.raises(LexerError) as exc_info:
            tokenize(r"\k")
        err = exc_info.value
        assert "k" in err.message

    def test_unrecognised_escape_col_points_at_backslash(self):
        with pytest.raises(LexerError) as exc_info:
            tokenize(r"ab\k")
        # The backslash is at index 2 → column 3
        assert exc_info.value.position == 3

    def test_unrecognised_escape_char_field(self):
        with pytest.raises(LexerError) as exc_info:
            tokenize(r"\k")
        # char carries the full escape sequence
        assert "k" in exc_info.value.char


# ─────────────────────────────────────────────────────────────────────────────
# 17. LexerError structured payload
# ─────────────────────────────────────────────────────────────────────────────

class TestLexerErrorStructure:

    def test_to_dict_always_has_error_and_message(self):
        err = LexerError("bad char", position=3, char="€")
        d = err.to_dict()
        assert d["error"] == "LEXER_ERROR"
        assert d["message"] == "bad char"

    def test_to_dict_position_dict(self):
        err = LexerError("bad", position=5)
        d = err.to_dict()
        assert d["position"] == {"line": 1, "column": 5}

    def test_to_dict_char_field(self):
        err = LexerError("bad", char="€")
        d = err.to_dict()
        assert d["char"] == "€"

    def test_to_dict_no_position_when_none(self):
        err = LexerError("oops")
        assert "position" not in err.to_dict()

    def test_to_dict_no_char_when_none(self):
        err = LexerError("oops")
        assert "char" not in err.to_dict()

    def test_status_code_is_400(self):
        err = LexerError("oops")
        assert err.status_code == 400


# ─────────────────────────────────────────────────────────────────────────────
# 18. EOF is always the last token
# ─────────────────────────────────────────────────────────────────────────────

class TestEOFAlwaysLast:

    @pytest.mark.parametrize("pattern", [
        "",
        "a",
        "(a|b)*abb",
        "[a-z]+",
        r"a\*b",
        "abc|def",
    ])
    def test_eof_is_last(self, pattern: str):
        tokens = tokenize(pattern)
        assert tokens[-1].type is TokenType.EOF

    @pytest.mark.parametrize("pattern", [
        "",
        "a",
        "(a|b)*abb",
        "[a-z]+",
    ])
    def test_exactly_one_eof(self, pattern: str):
        tokens = tokenize(pattern)
        eof_count = sum(1 for t in tokens if t.type is TokenType.EOF)
        assert eof_count == 1


# ─────────────────────────────────────────────────────────────────────────────
# 19. Column positions are correct and 1-indexed
# ─────────────────────────────────────────────────────────────────────────────

class TestColumnPositions:

    def test_all_columns_positive(self):
        for tok in tokenize("a|b*c"):
            assert tok.column >= 1, f"Column should be ≥1, got {tok.column} for {tok!r}"

    def test_first_token_col_is_one(self):
        assert tokenize("abc")[0].column == 1

    def test_consecutive_single_chars(self):
        tokens = tokenize("abc")
        cols = [t.column for t in tokens[:-1]]  # exclude EOF
        assert cols == [1, 2, 3]

    def test_escape_sequence_column_is_backslash_col(self):
        # Pattern: `a\*b`  — backslash is at index 1 → column 2
        tokens = tokenize(r"a\*b")
        assert tokens[1].column == 2

    def test_eof_column_is_len_plus_one(self):
        pattern = "abc"
        tokens = tokenize(pattern)
        assert tokens[-1].column == len(pattern) + 1


# ─────────────────────────────────────────────────────────────────────────────
# 20. Unicode literals
# ─────────────────────────────────────────────────────────────────────────────

class TestUnicodeLiterals:

    def test_accented_char_is_char_token(self):
        tokens = tokenize("é")
        assert tokens[0].type is TokenType.CHAR
        assert tokens[0].value == "é"

    def test_cjk_char_is_char_token(self):
        tokens = tokenize("中")
        assert tokens[0].type is TokenType.CHAR
        assert tokens[0].value == "中"

    def test_emoji_is_char_token(self):
        # Emoji are printable unicode — valid literals
        tokens = tokenize("😀")
        assert tokens[0].type is TokenType.CHAR
