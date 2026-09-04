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

## Phase 4: Thompson's NFA Construction

Each AST node maps to an **NFA fragment** with exactly ONE start state and ONE
accepting state.  Fragments are composed by connecting them with ε-transitions.

### State / Transition Count Per Rule

| Rule           | New states | New ε-trans | New sym-trans | Notes |
|----------------|-----------|-------------|---------------|-------|
| Literal(c)     | 2         | 0           | 1             | q_s →[c]→ q_a |
| Epsilon        | 2         | 1           | 0             | q_s →[ε]→ q_a |
| CharClass      | 2         | 0           | `|chars|`     | One edge per char |
| Concat(L, R)   | 0         | 1           | 0             | bridge ε: L.accept → R.start |
| Union(L, R)    | 2         | 4           | 0             | fork + merge |
| Star(N)        | 2         | 4           | 0             | skip + enter + loop + exit |
| Plus(N)        | 1         | 2           | 0             | loop + exit (no skip) |
| Question(N)    | 2         | 3           | 0             | skip + enter + exit |

### State counts for `(a|b)*abb` (verified by tests)

| Step            | States | Sym | ε  | Total |
|-----------------|--------|-----|----|-------|
| Literal a (1)   |   2    |  1  |  0 |   1   |
| Literal b (2)   |  +2    | +1  |  0 |  +1   |
| Union(a,b)      |  +2    |  0  | +4 |  +4   |
| Star(union)     |  +2    |  0  | +4 |  +4   |
| Literal a (3)   |  +2    | +1  |  0 |  +1   |
| Concat(*,a)     |   0    |  0  | +1 |  +1   |
| Literal b (4)   |  +2    | +1  |  0 |  +1   |
| Concat(…,b)     |   0    |  0  | +1 |  +1   |
| Literal b (5)   |  +2    | +1  |  0 |  +1   |
| Concat(…,b)     |   0    |  0  | +1 |  +1   |
| **Total**       | **14** |**5**|**11**|**16**|

### Thompson Fragment Diagrams

```
STAR(N):
           ┌─────────── ε ──────────────┐
           │ ┌──────────────────────┐   │
           ▼ ▼                      │   │
    q_s ─ε─► N.start ──…── N.accept ─ε─┘
     │                               │
     └──────────── ε ───────────────► q_a

PLUS(N):
    N.start ──…── N.accept ─ε─► N.start  (loop)
                             └─ε─► q_a    (exit)

UNION(L, R):
             ┌──ε──► L.start ──…── L.accept ──ε──┐
    q_s ─────┤                                    ├──► q_a
             └──ε──► R.start ──…── R.accept ──ε──┘
```

### Simulation Algorithm (ε-closure + BFS)

```
function nfa_accepts(nfa, string):
    current ← ε_closure({nfa.start})
    for each char c in string:
        next ← {}
        for each state s in current:
            next ← next ∪ sym_map[s][c]   // symbol transitions
        current ← ε_closure(next)
    return current ∩ nfa.accepting ≠ ∅

function ε_closure(states):
    closure ← states
    stack   ← list(states)
    while stack not empty:
        s ← pop(stack)
        for each t in eps_map[s]:
            if t ∉ closure:
                closure ← closure ∪ {t}
                push(stack, t)
    return closure
```

Time complexity: O(|string| × |states|) per call after O(|states| + |transitions|)
precomputation of `eps_map` and `sym_map`.

Space: O(|states|) for current state set.

### ε-closure Invariants (verified by tests)

| Pattern | ε-closure({start}) contains accepting? | Reason |
|---------|----------------------------------------|--------|
| a*      | YES | Skip ε-edge: start→accept |
| a?      | YES | Skip ε-edge: start→accept |
| a+      | NO  | Must enter body at least once |
| a       | NO  | Only 1 symbol transition |

---

*This document will be extended as Phases 5–7 are implemented.*
