"""
Phase 2 — AST node unit tests.

These tests exercise node construction and serialisation in isolation,
without invoking the parser.  They verify:
  1.  Each node type can be constructed and is hashable (frozen dataclass).
  2.  ``to_dict()`` returns exactly the expected structure for every type.
  3.  JSON serialisation round-trips through ``json.dumps / json.loads``.
  4.  Nested trees serialise recursively.
  5.  ``EpsilonNode`` and ``DotNode`` serialise correctly.
  6.  ``ClassRange`` serialises single-char and range forms correctly.
  7.  ``CharClassNode`` with negate=True serialises correctly.
  8.  Equality (``==``) works on all nodes (enables direct AST comparisons
      in test_parser.py without hand-rolling assertions).
"""

from __future__ import annotations

import json

import pytest

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


# ── 1. Construction and hashability ───────────────────────────────────────────

class TestConstruction:

    def test_literal_node_stores_char(self):
        n = LiteralNode("a")
        assert n.char == "a"

    def test_literal_node_is_hashable(self):
        s = {LiteralNode("a"), LiteralNode("b"), LiteralNode("a")}
        assert len(s) == 2

    def test_concat_node_stores_children(self):
        l, r = LiteralNode("a"), LiteralNode("b")
        n = ConcatNode(l, r)
        assert n.left is l
        assert n.right is r

    def test_union_node_stores_children(self):
        l, r = LiteralNode("x"), LiteralNode("y")
        n = UnionNode(l, r)
        assert n.left is l and n.right is r

    def test_star_node_stores_child(self):
        c = LiteralNode("a")
        assert StarNode(c).child is c

    def test_plus_node_stores_child(self):
        c = LiteralNode("b")
        assert PlusNode(c).child is c

    def test_question_node_stores_child(self):
        c = LiteralNode("c")
        assert QuestionNode(c).child is c

    def test_epsilon_node_is_singleton_like(self):
        # Two EpsilonNodes must be equal
        assert EpsilonNode() == EpsilonNode()

    def test_dot_node_equals(self):
        assert DotNode() == DotNode()

    def test_char_class_range_single(self):
        r = ClassRange("a", "a")
        assert r.start == "a" and r.end == "a"

    def test_char_class_range_span(self):
        r = ClassRange("a", "z")
        assert r.start == "a" and r.end == "z"

    def test_char_class_node_stores_ranges(self):
        ranges = (ClassRange("a", "z"),)
        n = CharClassNode(negate=False, ranges=ranges)
        assert n.negate is False
        assert n.ranges == ranges

    def test_char_class_node_negated(self):
        n = CharClassNode(negate=True, ranges=(ClassRange("0", "9"),))
        assert n.negate is True


# ── 2. to_dict() for each node type ───────────────────────────────────────────

class TestToDict:

    def test_literal(self):
        assert LiteralNode("x").to_dict() == {"type": "Literal", "char": "x"}

    def test_epsilon(self):
        assert EpsilonNode().to_dict() == {"type": "Epsilon"}

    def test_dot(self):
        assert DotNode().to_dict() == {"type": "Dot"}

    def test_star(self):
        d = StarNode(LiteralNode("a")).to_dict()
        assert d == {"type": "Star", "child": {"type": "Literal", "char": "a"}}

    def test_plus(self):
        d = PlusNode(LiteralNode("b")).to_dict()
        assert d == {"type": "Plus", "child": {"type": "Literal", "char": "b"}}

    def test_question(self):
        d = QuestionNode(LiteralNode("c")).to_dict()
        assert d == {"type": "Question", "child": {"type": "Literal", "char": "c"}}

    def test_concat(self):
        d = ConcatNode(LiteralNode("a"), LiteralNode("b")).to_dict()
        assert d == {
            "type": "Concat",
            "left":  {"type": "Literal", "char": "a"},
            "right": {"type": "Literal", "char": "b"},
        }

    def test_union(self):
        d = UnionNode(LiteralNode("a"), LiteralNode("b")).to_dict()
        assert d == {
            "type": "Union",
            "left":  {"type": "Literal", "char": "a"},
            "right": {"type": "Literal", "char": "b"},
        }

    def test_class_range_single_char(self):
        assert ClassRange("a", "a").to_dict() == {"start": "a", "end": "a"}

    def test_class_range_span(self):
        assert ClassRange("0", "9").to_dict() == {"start": "0", "end": "9"}

    def test_char_class_not_negated(self):
        n = CharClassNode(negate=False, ranges=(ClassRange("a", "z"),))
        d = n.to_dict()
        assert d == {
            "type":   "CharClass",
            "negate": False,
            "ranges": [{"start": "a", "end": "z"}],
        }

    def test_char_class_negated(self):
        n = CharClassNode(negate=True, ranges=(ClassRange("0", "9"),))
        d = n.to_dict()
        assert d["negate"] is True

    def test_char_class_multi_range(self):
        ranges = (ClassRange("a", "z"), ClassRange("A", "Z"), ClassRange("0", "9"))
        d = CharClassNode(negate=False, ranges=ranges).to_dict()
        assert len(d["ranges"]) == 3
        assert d["ranges"][2] == {"start": "0", "end": "9"}


# ── 3. JSON serialisation round-trips ─────────────────────────────────────────

class TestJSONRoundTrip:

    def _rt(self, node: ASTNode) -> dict:
        """Serialise to JSON string and parse back."""
        return json.loads(json.dumps(node.to_dict()))

    def test_literal_json(self):
        assert self._rt(LiteralNode("q")) == {"type": "Literal", "char": "q"}

    def test_epsilon_json(self):
        assert self._rt(EpsilonNode()) == {"type": "Epsilon"}

    def test_dot_json(self):
        assert self._rt(DotNode()) == {"type": "Dot"}

    def test_star_json(self):
        d = self._rt(StarNode(LiteralNode("a")))
        assert d["type"] == "Star"
        assert d["child"]["char"] == "a"

    def test_nested_json(self):
        # Union(Star(a), Plus(b))
        tree = UnionNode(StarNode(LiteralNode("a")), PlusNode(LiteralNode("b")))
        d = self._rt(tree)
        assert d["type"] == "Union"
        assert d["left"]["type"] == "Star"
        assert d["right"]["type"] == "Plus"

    def test_char_class_json(self):
        n = CharClassNode(negate=False, ranges=(ClassRange("a", "z"),))
        d = self._rt(n)
        assert d["type"] == "CharClass"
        assert d["ranges"][0] == {"start": "a", "end": "z"}


# ── 4. Deep nested tree serialisation ─────────────────────────────────────────

class TestDeepNested:

    def test_concat_chain(self):
        """``abc`` → ConcatNode(ConcatNode(a, b), c)"""
        tree = ConcatNode(ConcatNode(LiteralNode("a"), LiteralNode("b")), LiteralNode("c"))
        d = tree.to_dict()
        assert d["type"] == "Concat"
        assert d["left"]["type"] == "Concat"
        assert d["left"]["left"] == {"type": "Literal", "char": "a"}
        assert d["right"] == {"type": "Literal", "char": "c"}

    def test_star_over_union(self):
        """``(a|b)*`` → StarNode(UnionNode(a, b))"""
        tree = StarNode(UnionNode(LiteralNode("a"), LiteralNode("b")))
        d = tree.to_dict()
        assert d["type"] == "Star"
        assert d["child"]["type"] == "Union"
        assert d["child"]["left"]["char"] == "a"
        assert d["child"]["right"]["char"] == "b"

    def test_complete_a_or_b_star_abb(self):
        """Full AST for ``(a|b)*abb``."""
        tree = ConcatNode(
            ConcatNode(
                ConcatNode(
                    StarNode(UnionNode(LiteralNode("a"), LiteralNode("b"))),
                    LiteralNode("a"),
                ),
                LiteralNode("b"),
            ),
            LiteralNode("b"),
        )
        d = tree.to_dict()
        # Outermost concat right is 'b'
        assert d["right"] == {"type": "Literal", "char": "b"}
        # One level in
        assert d["left"]["right"] == {"type": "Literal", "char": "b"}
        # Two levels in
        inner = d["left"]["left"]
        assert inner["left"]["type"] == "Star"
        assert inner["left"]["child"]["type"] == "Union"


# ── 5. Equality semantics ──────────────────────────────────────────────────────

class TestEquality:

    def test_same_literal_equal(self):
        assert LiteralNode("a") == LiteralNode("a")

    def test_different_literal_not_equal(self):
        assert LiteralNode("a") != LiteralNode("b")

    def test_concat_equality(self):
        n1 = ConcatNode(LiteralNode("a"), LiteralNode("b"))
        n2 = ConcatNode(LiteralNode("a"), LiteralNode("b"))
        assert n1 == n2

    def test_union_equality(self):
        n1 = UnionNode(LiteralNode("x"), LiteralNode("y"))
        n2 = UnionNode(LiteralNode("x"), LiteralNode("y"))
        assert n1 == n2

    def test_class_range_equality(self):
        assert ClassRange("a", "z") == ClassRange("a", "z")

    def test_char_class_equality(self):
        n1 = CharClassNode(False, (ClassRange("a", "z"),))
        n2 = CharClassNode(False, (ClassRange("a", "z"),))
        assert n1 == n2

    def test_type_mismatch_not_equal(self):
        assert LiteralNode("a") != StarNode(LiteralNode("a"))
