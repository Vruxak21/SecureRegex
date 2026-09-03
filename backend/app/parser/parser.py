"""
Recursive-descent parser for the SecureRegex regex subset.

Grammar implemented (EBNF — see docs/grammar.md for the full spec)
------------------------------------------------------------------
    regex        = alternation EOF
    alternation  = concatenation ( '|' concatenation )*
    concatenation = repetition+
    repetition   = primary ( '*' | '+' | '?' )*
    primary      = '(' alternation ')'
                 | char_class
                 | CHAR
                 | DOT
    char_class   = '[' '^'? class_item+ ']'
    class_item   = CHAR ( '-' CHAR )?

Precedence (tightest → loosest)
--------------------------------
    quantifiers  *  +  ?      (postfix on a single primary)
    concatenation              (implicit)
    alternation  |             (lowest)

All public entry points are ``parse()`` (takes a Token list) and the
convenience wrapper ``parse_pattern()`` (takes a raw string, calls the
lexer automatically).

Error policy
------------
Every error path raises ``ParseError`` (a ``SecureRegexError`` subclass)
with:
  * a human-readable ``message``
  * the 1-indexed ``position`` (column) of the offending token
  * an optional ``detail`` hint

Raw Python exceptions are never allowed to propagate to callers.
"""

from __future__ import annotations

from app.ast import (
    ASTNode,
    CharClassNode,
    ClassRange,
    ConcatNode,
    DotNode,
    LiteralNode,
    PlusNode,
    QuestionNode,
    StarNode,
    UnionNode,
)
from app.exceptions import ParseError
from app.lexer.token import Token, TokenType

# Token types that can begin a primary expression
_PRIMARY_FIRST = frozenset({
    TokenType.CHAR,
    TokenType.DOT,
    TokenType.LPAREN,
    TokenType.LBRACKET,
})

# Token types that terminate a concatenation sequence
_CONCAT_STOP = frozenset({
    TokenType.OR,
    TokenType.RPAREN,
    TokenType.EOF,
})


# ── Parser class ──────────────────────────────────────────────────────────────

class Parser:
    """Hand-written recursive-descent parser.

    Instantiate with the Token list from ``app.lexer.tokenize()``, then
    call ``parse()`` to get the root ``ASTNode``.
    """

    def __init__(self, tokens: list[Token]) -> None:
        if not tokens:
            raise ParseError(
                "Token list is empty — call tokenize() before parse().",
                position=1,
            )
        self._tokens = tokens
        self._pos    = 0

    # ── Token stream helpers ──────────────────────────────────────────────

    def _current(self) -> Token:
        return self._tokens[self._pos]

    def _peek_type(self) -> TokenType:
        return self._tokens[self._pos].type

    def _at_eof(self) -> bool:
        return self._peek_type() is TokenType.EOF

    def _consume(self, expected: TokenType | None = None) -> Token:
        """Return the current token and advance.  Raises ``ParseError`` if
        the current type doesn't match *expected* (when given)."""
        tok = self._tokens[self._pos]
        if expected is not None and tok.type is not expected:
            raise ParseError(
                f"Expected {expected.name} but found "
                f"'{tok.value or tok.type.name}' at column {tok.column}.",
                position=tok.column,
                detail=f"Token type mismatch: wanted {expected.name}, got {tok.type.name}.",
            )
        self._pos += 1
        return tok

    # ── Grammar rules ─────────────────────────────────────────────────────

    def parse(self) -> ASTNode:
        """Entry point — parse the full token stream and return the AST root."""
        node = self._parse_alternation()

        # After a complete expression we must be sitting on EOF.
        if not self._at_eof():
            tok = self._current()
            raise ParseError(
                f"Unexpected token '{tok.value or tok.type.name}' "
                f"at column {tok.column}.",
                position=tok.column,
                detail=(
                    "The parser finished building an expression but found "
                    f"an extra '{tok.value or tok.type.name}'. "
                    "Check for unmatched parentheses or stray characters."
                ),
            )
        return node

    # ── alternation = concatenation ( '|' concatenation )* ───────────────

    def _parse_alternation(self) -> ASTNode:
        left = self._parse_concatenation()

        while self._peek_type() is TokenType.OR:
            or_tok = self._consume(TokenType.OR)

            # Empty right operand is a parse error
            if self._peek_type() in {TokenType.EOF, TokenType.RPAREN}:
                raise ParseError(
                    f"Expected an expression after '|' at column {or_tok.column}, "
                    f"but found '{self._current().value or 'EOF'}'.",
                    position=or_tok.column,
                    detail=(
                        "Alternation requires an expression on both sides of '|'. "
                        "If you want to match the empty string, use '?' on the "
                        "preceding group instead."
                    ),
                )

            right = self._parse_concatenation()
            left  = UnionNode(left, right)

        return left

    # ── concatenation = repetition+ ───────────────────────────────────────

    def _parse_concatenation(self) -> ASTNode:
        """Parse one or more repetitions and fold them left-associatively."""
        nodes: list[ASTNode] = []

        while self._peek_type() not in _CONCAT_STOP:
            nodes.append(self._parse_repetition())

        if not nodes:
            # This can only happen inside an empty group or after a leading '|'
            tok = self._current()
            raise ParseError(
                f"Empty expression at column {tok.column}: "
                "expected at least one term.",
                position=tok.column,
                detail=(
                    "An empty sub-expression was found. "
                    "Check for empty groups '()' or dangling '|' operators."
                ),
            )

        # Left-fold into a ConcatNode chain
        result = nodes[0]
        for node in nodes[1:]:
            result = ConcatNode(result, node)
        return result

    # ── repetition = primary quantifier* ─────────────────────────────────

    def _parse_repetition(self) -> ASTNode:
        """Parse a primary, then greedily consume any quantifiers.

        Consecutive quantifiers (e.g. ``a**``) are each applied in order,
        producing nested Nodes (e.g. ``StarNode(StarNode(a))``).  The
        semantic analyser in Phase 3 may reject such constructs.
        """
        # A bare quantifier with no preceding primary is an error
        if self._peek_type() in {TokenType.STAR, TokenType.PLUS, TokenType.QUESTION}:
            tok = self._current()
            raise ParseError(
                f"Quantifier '{tok.value}' at column {tok.column} "
                "has nothing to quantify.",
                position=tok.column,
                detail=(
                    f"'{tok.value}' must follow a character, group, or "
                    "character class, not appear at the start of an expression."
                ),
            )

        node = self._parse_primary()

        while self._peek_type() in {TokenType.STAR, TokenType.PLUS, TokenType.QUESTION}:
            q = self._consume()
            match q.type:
                case TokenType.STAR:     node = StarNode(node)
                case TokenType.PLUS:     node = PlusNode(node)
                case TokenType.QUESTION: node = QuestionNode(node)

        return node

    # ── primary = '(' alt ')' | char_class | CHAR | DOT ──────────────────

    def _parse_primary(self) -> ASTNode:
        tok = self._current()

        match tok.type:
            # ── Grouped sub-expression ────────────────────────────────────
            case TokenType.LPAREN:
                open_tok = self._consume(TokenType.LPAREN)

                # Empty group `()` is a parse error
                if self._peek_type() is TokenType.RPAREN:
                    raise ParseError(
                        f"Empty group '()' at column {open_tok.column}.",
                        position=open_tok.column,
                        detail=(
                            "An empty pair of parentheses matches nothing. "
                            "Put at least one character or sub-expression inside."
                        ),
                    )

                node = self._parse_alternation()

                if self._peek_type() is not TokenType.RPAREN:
                    # Missing closing paren — report at the opening '('
                    raise ParseError(
                        f"Missing closing ')' for '(' at column {open_tok.column}.",
                        position=open_tok.column,
                        detail=(
                            "Every '(' must be matched by a ')'. "
                            f"Found '{self._current().value or 'EOF'}' instead."
                        ),
                    )
                self._consume(TokenType.RPAREN)
                return node

            # ── Character class ───────────────────────────────────────────
            case TokenType.LBRACKET:
                return self._parse_char_class()

            # ── Literal character ─────────────────────────────────────────
            case TokenType.CHAR:
                self._consume()
                return LiteralNode(tok.value)

            # ── Wildcard dot ──────────────────────────────────────────────
            case TokenType.DOT:
                self._consume()
                return DotNode()

            # ── Anything else is unexpected ───────────────────────────────
            case _:
                label = tok.value if tok.value else tok.type.name
                raise ParseError(
                    f"Unexpected token '{label}' at column {tok.column}.",
                    position=tok.column,
                    detail=(
                        f"The parser expected a character, '(', or '[' "
                        f"but encountered '{label}'."
                    ),
                )

    # ── char_class = '[' '^'? class_item+ ']' ────────────────────────────

    def _parse_char_class(self) -> ASTNode:
        open_tok = self._consume(TokenType.LBRACKET)

        # Optional negation
        negate = False
        if self._peek_type() is TokenType.CARET:
            self._consume(TokenType.CARET)
            negate = True

        ranges: list[ClassRange] = []

        while self._peek_type() not in {TokenType.RBRACKET, TokenType.EOF}:
            cur = self._current()

            # A DASH at the very start (or after negation) is a literal '-'
            if cur.type is TokenType.DASH:
                self._consume(TokenType.DASH)
                ranges.append(ClassRange("-", "-"))
                continue

            if cur.type is not TokenType.CHAR:
                raise ParseError(
                    f"Unexpected token '{cur.value}' inside character class "
                    f"at column {cur.column}.",
                    position=cur.column,
                )

            start_tok = self._consume(TokenType.CHAR)

            # Check for a range  a-z
            if self._peek_type() is TokenType.DASH:
                self._consume(TokenType.DASH)

                if self._peek_type() is TokenType.CHAR:
                    # Well-formed range
                    end_tok = self._consume(TokenType.CHAR)
                    if ord(end_tok.value) < ord(start_tok.value):
                        raise ParseError(
                            f"Invalid character range '{start_tok.value}-{end_tok.value}' "
                            f"at column {start_tok.column}: "
                            "start must be ≤ end in Unicode codepoint order.",
                            position=start_tok.column,
                            detail=(
                                f"'{start_tok.value}' (U+{ord(start_tok.value):04X}) "
                                f"> '{end_tok.value}' (U+{ord(end_tok.value):04X})."
                            ),
                        )
                    ranges.append(ClassRange(start_tok.value, end_tok.value))
                else:
                    # Trailing dash — treat char and dash as two literals
                    ranges.append(ClassRange(start_tok.value, start_tok.value))
                    ranges.append(ClassRange("-", "-"))
            else:
                ranges.append(ClassRange(start_tok.value, start_tok.value))

        # Unclosed bracket
        if self._peek_type() is TokenType.EOF:
            raise ParseError(
                f"Unclosed character class '[' at column {open_tok.column}.",
                position=open_tok.column,
                detail="Every '[' must be matched by a ']'.",
            )

        # Empty class  []  or  [^]
        if not ranges:
            raise ParseError(
                f"Empty character class at column {open_tok.column}.",
                position=open_tok.column,
                detail="A character class must contain at least one character or range.",
            )

        self._consume(TokenType.RBRACKET)
        return CharClassNode(negate=negate, ranges=tuple(ranges))


# ── Public API ─────────────────────────────────────────────────────────────────

def parse(tokens: list[Token]) -> ASTNode:
    """Parse a flat token list (from :func:`app.lexer.tokenize`) into an AST.

    Parameters
    ----------
    tokens : list[Token]
        Must include the terminating ``EOF`` token.

    Returns
    -------
    ASTNode
        The root of the Abstract Syntax Tree.

    Raises
    ------
    ParseError
        On any syntactic error, with position and detail set.
    """
    return Parser(tokens).parse()


def parse_pattern(pattern: str, max_length: int | None = None) -> ASTNode:
    """Convenience wrapper: lex *pattern* then parse it.

    Parameters
    ----------
    pattern    : str        – Raw regex string.
    max_length : int | None – Forwarded to the lexer's length guard.

    Returns
    -------
    ASTNode
        Root of the AST.

    Raises
    ------
    RegexTooLongError
        If the pattern exceeds ``max_length``.
    LexerError
        On any lexical error.
    ParseError
        On any syntactic error.
    """
    from app.lexer import tokenize
    tokens = tokenize(pattern, max_length=max_length)
    return parse(tokens)
