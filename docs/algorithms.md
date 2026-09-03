# SecureRegex — Algorithms & Design Reference

This document records the design decisions, algorithms, and semantic rules
used across the compiler pipeline.

---

## Phase 3: Semantic Analysis

The semantic analyser performs a single depth-first, left-to-right walk of
the AST.  It produces a flat list of `Diagnostic` objects — it never raises
an exception and never mutates the tree.

### Diagnostic structure

```json
{
  "severity": "ERROR | WARNING",
  "code":     "SEMxxx",
  "message":  "human-readable description",
  "position": { "line": 1, "column": N }   // omitted when unknown
}
```

### Pipeline policy

| Highest severity in list | Pipeline action |
|--------------------------|-----------------|
| ERROR                    | Stop; return diagnostics to caller |
| WARNING                  | Continue; diagnostics attached to report |
| (empty)                  | Continue normally |

### Semantic Rules Reference

#### SEM001 — Invalid character class range  `ERROR`

**When**: A `ClassRange` node has `ord(end) < ord(start)`.

**Example**: `[z-a]` — `z` (U+007A) > `a` (U+0061).

**Rationale**: An empty range makes the whole character class unmatchable.
Most regex engines reject this; others silently produce an empty class.
SecureRegex treats it as an error so users get immediate feedback rather
than a confusing "pattern never matches" result.

**Position**: Reports the column of the *start* character of the range
(e.g. column 2 for `[z-a]`).

**Example diagnostic**:
```json
{
  "severity": "ERROR",
  "code": "SEM001",
  "message": "Invalid character class range 'z'-'a': start codepoint U+007A is greater than end codepoint U+0061. Ranges must be in ascending Unicode order.",
  "position": {"line": 1, "column": 2}
}
```

---

#### SEM002 — Redundant consecutive quantifier  `WARNING`

**When**: A quantifier node (`StarNode`, `PlusNode`, `QuestionNode`) directly
wraps another quantifier node.

**Examples**: `a**`, `b+?`, `c?*`

**Rationale**: In standard regex semantics, `a**` ≡ `a*` and `a+?` ≡ `a?`.
The outer quantifier makes the inner one redundant.  This pattern almost
always indicates a typo.

**Position**: Reports the column of the *outer* quantifier token.

**Why WARNING not ERROR**: The pattern is unambiguous — the engine can still
run it correctly (it just nests the NFA constructs).  Blocking it would be
overly strict for an academic tool.

---

#### SEM003 — Unsupported construct: dot wildcard  `ERROR`

**When**: A `DotNode` is encountered in the AST.

**Example**: `a.b`

**Rationale**: The `.` wildcard is lexed and parsed (to give a clear error
rather than a confusing token mismatch), but the v1 NFA/DFA engine does not
implement it.  Returning a result would silently match incorrectly.

**Position**: Reports the column of the `.` character.

**Upgrade path**: Phase 5 will implement `.` as the union of all characters
in the input alphabet, making this rule obsolete.

---

#### SEM004 — Negated character class  `WARNING`

**When**: A `CharClassNode` has `negate=True`.

**Example**: `[^a-z]`

**Rationale**: Negated classes are fully lexed and parsed (`[^…]` → 
`CharClassNode(negate=True, …)`), but the v1 NFA/DFA builder ignores the
negation flag.  The automaton treats `[^a-z]` as `[a-z]`, producing incorrect
matches.

**Position**: Reports the column of the opening `[`.

**Why WARNING not ERROR**: Power users may build tooling that pre-processes
the AST and implement negation themselves.  A warning allows the pipeline to
continue and return partial results while still surfacing the risk.

**Upgrade path**: Phase 5 will implement negated classes by computing the
complement of the range set against the full alphabet.

---

### Walker algorithm

```
procedure walk(node):
    match type(node):
        LiteralNode | EpsilonNode:
            return   // always valid

        DotNode:
            emit SEM003
            return

        CharClassNode:
            for each range in node.ranges:
                if ord(range.end) < ord(range.start):
                    emit SEM001
            if node.negate:
                emit SEM004
            return   // no child nodes

        StarNode | PlusNode | QuestionNode:
            if type(node.child) in {StarNode, PlusNode, QuestionNode}:
                emit SEM002
            walk(node.child)

        ConcatNode:
            walk(node.left)
            walk(node.right)

        UnionNode:
            walk(node.left)
            walk(node.right)
```

Time complexity: O(n) where n = number of AST nodes (single pass).  
Space complexity: O(d) for the call stack, where d = maximum nesting depth.

---

## Phase 1: Lexer

The lexer is a single-pass, character-by-character scanner with one boolean
state variable `in_bracket` that tracks whether the scanner is inside a
`[…]` character class.  This allows `-`, `^`, and `]` to receive their
special token types only in that context.

Time complexity: O(n) where n = length of the input string.

---

## Phase 2: Parser

A hand-written recursive-descent parser with five grammar rules
(`alternation`, `concatenation`, `repetition`, `primary`, `char_class`).
Precedence is encoded structurally: higher-precedence operators are deeper
in the call chain.

| Operator | Precedence | Rule |
|----------|-----------|------|
| `* + ?`  | 1 (highest) | `repetition` |
| Concat   | 2 | `concatenation` |
| `\|`     | 3 (lowest) | `alternation` |

All binary nodes are left-associative.  
Time complexity: O(n) where n = number of tokens.

---

*This document will be extended as Phases 4–7 are implemented.*
