"""
Phase 2 — Parser tests.

Coverage targets
----------------
1.  Single literal
2.  Concatenation  — left-associativity, shape
3.  Alternation    — left-associativity, multiple branches
4.  Quantifiers    — *, +, ?  individually and chained
5.  Nested groups  — (a|b)*, ((ab)+|c?)
6.  Character classes — [a-z], [^abc], [0-9], multi-range, leading/trailing dash
7.  Inverted range [z-a] → ParseError with position
8.  Error: unbalanced open paren
9.  Error: unbalanced close paren
10. Error: empty group ()
11. Error: dangling | (right side empty)
12. Error: leading | (left side missing)
13. Error: bare quantifier * + ? at start or after |
14. Error: unclosed character class [
15. Error: empty character class []
16. ParseError carries position and structured to_dict()
17. parse_pattern() convenience wrapper works end-to-end
18. Exact AST shape for (a|b)* matches Star(Union(a, b))
19. Exact AST shape for (a|b)*abb verified node-by-node
20. DOT token produces DotNode
21. Escape sequences in patterns tokenised and parsed to LiteralNode
22. Complex pattern (ab)+|[0-9]* — full structural verification
"""

from __future__ import annotations

import json

import pytest

from app.ast import (
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
from app.parser import parse_pattern
from app.lexer import tokenize
from app.parser import parse


# ── Helpers ───────────────────────────────────────────────────────────────────

def pp(pattern: str):
    """Shorthand: lex + parse a pattern string."""
    return parse_pattern(pattern)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Single literal
# ─────────────────────────────────────────────────────────────────────────────

class TestSingleLiteral:

    def test_single_letter(self):
        assert pp("a") == LiteralNode("a")

    def test_single_digit(self):
        assert pp("5") == LiteralNode("5")

    def test_single_unicode(self):
        assert pp("é") == LiteralNode("é")

    def test_escaped_paren_is_literal(self):
        assert pp(r"\(") == LiteralNode("(")

    def test_escaped_star_is_literal(self):
        assert pp(r"\*") == LiteralNode("*")


# ─────────────────────────────────────────────────────────────────────────────
# 2. Concatenation
# ─────────────────────────────────────────────────────────────────────────────

class TestConcatenation:

    def test_two_chars(self):
        assert pp("ab") == ConcatNode(LiteralNode("a"), LiteralNode("b"))

    def test_three_chars_left_assoc(self):
        # abc  →  Concat(Concat(a, b), c)
        expected = ConcatNode(
            ConcatNode(LiteralNode("a"), LiteralNode("b")),
            LiteralNode("c"),
        )
        assert pp("abc") == expected

    def test_four_chars(self):
        node = pp("abcd")
        assert node.right == LiteralNode("d")          # type: ignore[union-attr]
        assert node.left.right == LiteralNode("c")     # type: ignore[union-attr]

    def test_concat_dict_type(self):
        assert pp("ab").to_dict()["type"] == "Concat"


# ─────────────────────────────────────────────────────────────────────────────
# 3. Alternation
# ─────────────────────────────────────────────────────────────────────────────

class TestAlternation:

    def test_simple_union(self):
        assert pp("a|b") == UnionNode(LiteralNode("a"), LiteralNode("b"))

    def test_left_associativity(self):
        # a|b|c  →  Union(Union(a, b), c)
        expected = UnionNode(
            UnionNode(LiteralNode("a"), LiteralNode("b")),
            LiteralNode("c"),
        )
        assert pp("a|b|c") == expected

    def test_alternation_of_concats(self):
        # ab|cd  →  Union(Concat(a,b), Concat(c,d))
        expected = UnionNode(
            ConcatNode(LiteralNode("a"), LiteralNode("b")),
            ConcatNode(LiteralNode("c"), LiteralNode("d")),
        )
        assert pp("ab|cd") == expected

    def test_union_dict_type(self):
        assert pp("a|b").to_dict()["type"] == "Union"


# ─────────────────────────────────────────────────────────────────────────────
# 4. Quantifiers
# ─────────────────────────────────────────────────────────────────────────────

class TestQuantifiers:

    def test_star(self):
        assert pp("a*") == StarNode(LiteralNode("a"))

    def test_plus(self):
        assert pp("a+") == PlusNode(LiteralNode("a"))

    def test_question(self):
        assert pp("a?") == QuestionNode(LiteralNode("a"))

    def test_star_on_group(self):
        node = pp("(ab)*")
        assert isinstance(node, StarNode)
        assert node.child == ConcatNode(LiteralNode("a"), LiteralNode("b"))

    def test_quantifier_binds_tighter_than_concat(self):
        # ab*  →  Concat(a, Star(b))
        assert pp("ab*") == ConcatNode(LiteralNode("a"), StarNode(LiteralNode("b")))

    def test_quantifier_binds_tighter_than_union(self):
        # a|b*  →  Union(a, Star(b))
        assert pp("a|b*") == UnionNode(LiteralNode("a"), StarNode(LiteralNode("b")))

    def test_multiple_quantifiers_nest(self):
        # a**  →  Star(Star(a))   — not great regex but valid syntactically
        node = pp("a**")
        assert isinstance(node, StarNode)
        assert isinstance(node.child, StarNode)

    def test_plus_dict_type(self):
        assert pp("a+").to_dict()["type"] == "Plus"

    def test_question_dict_type(self):
        assert pp("a?").to_dict()["type"] == "Question"


# ─────────────────────────────────────────────────────────────────────────────
# 5. Nested groups
# ─────────────────────────────────────────────────────────────────────────────

class TestNestedGroups:

    def test_group_strips_parens(self):
        # (a)  →  LiteralNode('a')  — parens don't produce their own node
        assert pp("(a)") == LiteralNode("a")

    def test_double_parens(self):
        assert pp("((a))") == LiteralNode("a")

    def test_star_over_group(self):
        node = pp("(a|b)*")
        assert node == StarNode(UnionNode(LiteralNode("a"), LiteralNode("b")))

    def test_nested_groups_complex(self):
        # ((ab)+|c?)
        node = pp("((ab)+|c?)")
        expected = UnionNode(
            PlusNode(ConcatNode(LiteralNode("a"), LiteralNode("b"))),
            QuestionNode(LiteralNode("c")),
        )
        assert node == expected

    def test_group_inside_concat(self):
        # a(b|c)d  →  Concat(Concat(a, Union(b,c)), d)
        node = pp("a(b|c)d")
        assert isinstance(node, ConcatNode)
        assert node.right == LiteralNode("d")
        assert node.left.right == UnionNode(LiteralNode("b"), LiteralNode("c"))  # type: ignore


# ─────────────────────────────────────────────────────────────────────────────
# 6. Character classes
# ─────────────────────────────────────────────────────────────────────────────

class TestCharacterClasses:

    def test_simple_range(self):
        node = pp("[a-z]")
        assert node == CharClassNode(negate=False, ranges=(ClassRange("a", "z"),))

    def test_digit_range(self):
        node = pp("[0-9]")
        assert node == CharClassNode(negate=False, ranges=(ClassRange("0", "9"),))

    def test_single_char_class(self):
        node = pp("[x]")
        assert node == CharClassNode(negate=False, ranges=(ClassRange("x", "x"),))

    def test_multi_range(self):
        node = pp("[a-zA-Z0-9]")
        assert isinstance(node, CharClassNode)
        assert len(node.ranges) == 3

    def test_negated_class(self):
        node = pp("[^a-z]")
        assert isinstance(node, CharClassNode)
        assert node.negate is True
        assert node.ranges == (ClassRange("a", "z"),)

    def test_class_with_quantifier(self):
        node = pp("[a-z]+")
        assert isinstance(node, PlusNode)
        assert isinstance(node.child, CharClassNode)

    def test_leading_dash_is_literal(self):
        # [-a]  →  CharClass with '-' as literal, then 'a'
        node = pp("[-a]")
        assert isinstance(node, CharClassNode)
        assert ClassRange("-", "-") in node.ranges
        assert ClassRange("a", "a") in node.ranges

    def test_char_class_dict_type(self):
        assert pp("[a-z]").to_dict()["type"] == "CharClass"


# ─────────────────────────────────────────────────────────────────────────────
# 7. Inverted character range
# ─────────────────────────────────────────────────────────────────────────────

class TestInvalidRange:

    def test_inverted_range_raises(self):
        with pytest.raises(ParseError) as exc_info:
            pp("[z-a]")
        assert exc_info.value.error_code == "PARSE_ERROR"

    def test_inverted_range_mentions_chars(self):
        with pytest.raises(ParseError) as exc_info:
            pp("[z-a]")
        assert "z" in exc_info.value.message and "a" in exc_info.value.message

    def test_inverted_range_has_position(self):
        with pytest.raises(ParseError) as exc_info:
            pp("[z-a]")
        assert exc_info.value.position is not None


# ─────────────────────────────────────────────────────────────────────────────
# 8. Unbalanced open paren
# ─────────────────────────────────────────────────────────────────────────────

class TestUnbalancedOpenParen:

    def test_missing_close(self):
        with pytest.raises(ParseError) as exc_info:
            pp("(a|b")
        assert ")" in exc_info.value.message

    def test_missing_close_position(self):
        with pytest.raises(ParseError) as exc_info:
            pp("(a|b")
        # '(' is at column 1
        assert exc_info.value.position == 1

    def test_nested_missing_close(self):
        with pytest.raises(ParseError):
            pp("((a|b)")


# ─────────────────────────────────────────────────────────────────────────────
# 9. Unbalanced close paren
# ─────────────────────────────────────────────────────────────────────────────

class TestUnbalancedCloseParen:

    def test_extra_close(self):
        with pytest.raises(ParseError) as exc_info:
            pp("a|b)")
        assert exc_info.value.error_code == "PARSE_ERROR"

    def test_extra_close_position(self):
        with pytest.raises(ParseError) as exc_info:
            pp("a)")
        # ')' is at column 2
        assert exc_info.value.position == 2


# ─────────────────────────────────────────────────────────────────────────────
# 10. Empty group
# ─────────────────────────────────────────────────────────────────────────────

class TestEmptyGroup:

    def test_empty_group_raises(self):
        with pytest.raises(ParseError) as exc_info:
            pp("()")
        assert "empty" in exc_info.value.message.lower()

    def test_empty_group_position(self):
        with pytest.raises(ParseError) as exc_info:
            pp("a()")
        # '(' is at column 2
        assert exc_info.value.position == 2

    def test_empty_group_error_code(self):
        with pytest.raises(ParseError) as exc_info:
            pp("()")
        assert exc_info.value.error_code == "PARSE_ERROR"


# ─────────────────────────────────────────────────────────────────────────────
# 11 & 12. Dangling | operator
# ─────────────────────────────────────────────────────────────────────────────

class TestDanglingOperator:

    def test_trailing_pipe_raises(self):
        with pytest.raises(ParseError) as exc_info:
            pp("a|")
        assert "|" in exc_info.value.message

    def test_trailing_pipe_position(self):
        with pytest.raises(ParseError) as exc_info:
            pp("a|")
        # '|' is at column 2
        assert exc_info.value.position == 2

    def test_leading_pipe_raises(self):
        with pytest.raises(ParseError):
            pp("|a")

    def test_double_pipe_raises(self):
        with pytest.raises(ParseError):
            pp("a||b")


# ─────────────────────────────────────────────────────────────────────────────
# 13. Bare quantifiers
# ─────────────────────────────────────────────────────────────────────────────

class TestBareQuantifiers:

    def test_leading_star_raises(self):
        with pytest.raises(ParseError) as exc_info:
            pp("*a")
        assert "*" in exc_info.value.message

    def test_leading_plus_raises(self):
        with pytest.raises(ParseError) as exc_info:
            pp("+a")
        assert "+" in exc_info.value.message

    def test_leading_question_raises(self):
        with pytest.raises(ParseError) as exc_info:
            pp("?a")
        assert "?" in exc_info.value.message

    def test_quantifier_after_pipe_raises(self):
        with pytest.raises(ParseError):
            pp("a|*b")

    def test_bare_star_position(self):
        with pytest.raises(ParseError) as exc_info:
            pp("*")
        assert exc_info.value.position == 1


# ─────────────────────────────────────────────────────────────────────────────
# 14 & 15. Unclosed / empty character class
# ─────────────────────────────────────────────────────────────────────────────

class TestCharClassErrors:

    def test_unclosed_bracket_raises(self):
        with pytest.raises(ParseError) as exc_info:
            pp("[a-z")
        assert "[" in exc_info.value.message or "unclosed" in exc_info.value.message.lower()

    def test_unclosed_bracket_position(self):
        with pytest.raises(ParseError) as exc_info:
            pp("a[b-z")
        # '[' is at column 2
        assert exc_info.value.position == 2

    def test_empty_class_raises(self):
        with pytest.raises(ParseError) as exc_info:
            pp("[]")
        assert "empty" in exc_info.value.message.lower()

    def test_empty_negated_class_raises(self):
        with pytest.raises(ParseError):
            pp("[^]")


# ─────────────────────────────────────────────────────────────────────────────
# 16. ParseError structure
# ─────────────────────────────────────────────────────────────────────────────

class TestParseErrorStructure:

    def test_error_code(self):
        try:
            pp("(")
        except ParseError as e:
            assert e.error_code == "PARSE_ERROR"

    def test_status_code_is_400(self):
        try:
            pp("(")
        except ParseError as e:
            assert e.status_code == 400

    def test_to_dict_has_position(self):
        try:
            pp("(")
        except ParseError as e:
            d = e.to_dict()
            assert "position" in d
            assert d["position"]["line"] == 1

    def test_to_dict_no_position_when_none(self):
        from app.exceptions import ParseError as PE
        err = PE("oops")
        assert "position" not in err.to_dict()


# ─────────────────────────────────────────────────────────────────────────────
# 17. parse_pattern() convenience wrapper
# ─────────────────────────────────────────────────────────────────────────────

class TestParsePatternWrapper:

    def test_returns_ast(self):
        from app.ast import ASTNode
        assert isinstance(pp("abc"), ASTNode)

    def test_identical_to_parse_plus_tokenize(self):
        tokens = tokenize("a|b*")
        assert parse(tokens) == pp("a|b*")

    def test_max_length_forwarded(self):
        from app.exceptions import RegexTooLongError
        with pytest.raises(RegexTooLongError):
            parse_pattern("a" * 100, max_length=10)


# ─────────────────────────────────────────────────────────────────────────────
# 18. Exact AST shape for (a|b)*
# ─────────────────────────────────────────────────────────────────────────────

class TestExactShapeStarUnion:

    def test_root_is_star(self):
        node = pp("(a|b)*")
        assert isinstance(node, StarNode)

    def test_child_is_union(self):
        node = pp("(a|b)*")
        assert isinstance(node.child, UnionNode)

    def test_union_left_is_a(self):
        node = pp("(a|b)*")
        assert node.child.left == LiteralNode("a")

    def test_union_right_is_b(self):
        node = pp("(a|b)*")
        assert node.child.right == LiteralNode("b")

    def test_full_equality(self):
        node = pp("(a|b)*")
        expected = StarNode(UnionNode(LiteralNode("a"), LiteralNode("b")))
        assert node == expected


# ─────────────────────────────────────────────────────────────────────────────
# 19. Exact AST for (a|b)*abb
# ─────────────────────────────────────────────────────────────────────────────

class TestExactShapeCanonical:

    @pytest.fixture
    def tree(self):
        return pp("(a|b)*abb")

    def test_root_is_concat(self, tree):
        assert isinstance(tree, ConcatNode)

    def test_rightmost_char_is_b(self, tree):
        assert tree.right == LiteralNode("b")

    def test_second_level_right_is_b(self, tree):
        assert tree.left.right == LiteralNode("b")  # type: ignore

    def test_innermost_right_is_a(self, tree):
        assert tree.left.left.right == LiteralNode("a")  # type: ignore

    def test_innermost_left_is_star(self, tree):
        star = tree.left.left.left  # type: ignore
        assert isinstance(star, StarNode)

    def test_star_child_is_union(self, tree):
        star = tree.left.left.left  # type: ignore
        assert isinstance(star.child, UnionNode)

    def test_full_equality(self, tree):
        expected = ConcatNode(
            ConcatNode(
                ConcatNode(
                    StarNode(UnionNode(LiteralNode("a"), LiteralNode("b"))),
                    LiteralNode("a"),
                ),
                LiteralNode("b"),
            ),
            LiteralNode("b"),
        )
        assert tree == expected

    def test_json_serialisation(self, tree):
        d = json.loads(json.dumps(tree.to_dict()))
        assert d["type"] == "Concat"
        # Dig to the Star node
        star = d["left"]["left"]["left"]
        assert star["type"] == "Star"
        assert star["child"]["type"] == "Union"
        assert star["child"]["left"] == {"type": "Literal", "char": "a"}
        assert star["child"]["right"] == {"type": "Literal", "char": "b"}


# ─────────────────────────────────────────────────────────────────────────────
# 20. DOT token
# ─────────────────────────────────────────────────────────────────────────────

class TestDot:

    def test_dot_produces_dot_node(self):
        assert pp(".") == DotNode()

    def test_dot_in_concat(self):
        node = pp("a.b")
        assert isinstance(node, ConcatNode)
        assert node.left.right == DotNode()  # type: ignore


# ─────────────────────────────────────────────────────────────────────────────
# 21. Escape sequences parsed correctly
# ─────────────────────────────────────────────────────────────────────────────

class TestEscapeInParser:

    def test_escaped_paren_is_literal(self):
        node = pp(r"a\(b")
        # Concat(Concat(a, Literal('(')), b)
        assert isinstance(node, ConcatNode)
        assert node.left.right == LiteralNode("(")   # type: ignore

    def test_escaped_star_in_concat(self):
        node = pp(r"a\*")
        assert node == ConcatNode(LiteralNode("a"), LiteralNode("*"))

    def test_named_escape_n_is_literal(self):
        node = pp(r"\n")
        assert node == LiteralNode("\n")


# ─────────────────────────────────────────────────────────────────────────────
# 22. Complex pattern (ab)+|[0-9]*
# ─────────────────────────────────────────────────────────────────────────────

class TestComplexPattern:

    @pytest.fixture
    def tree(self):
        return pp("(ab)+|[0-9]*")

    def test_root_is_union(self, tree):
        assert isinstance(tree, UnionNode)

    def test_left_is_plus(self, tree):
        assert isinstance(tree.left, PlusNode)

    def test_plus_child_is_concat_ab(self, tree):
        concat = tree.left.child
        assert concat == ConcatNode(LiteralNode("a"), LiteralNode("b"))

    def test_right_is_star(self, tree):
        assert isinstance(tree.right, StarNode)

    def test_star_child_is_digit_class(self, tree):
        char_class = tree.right.child
        expected = CharClassNode(negate=False, ranges=(ClassRange("0", "9"),))
        assert char_class == expected
