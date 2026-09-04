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

## Phase 5: Subset Construction (NFA → DFA)

### Algorithm

```
function build_dfa(nfa, max_states):
    D0      ← ε_closure({nfa.start})          // start DFA state
    id_map  ← { D0: 0 }                        // NFA-set → DFA state ID
    worklist← [D0]

    while worklist not empty:
        S ← dequeue(worklist)
        for each symbol a in nfa.alphabet (sorted):
            T ← ε_closure({ q | p ∈ S, (p,a,q) ∈ nfa.transitions })
            if T is empty: continue            // implicit dead state — skip
            if T ∉ id_map:
                if |id_map| ≥ max_states: raise DFAConstructionError
                id_map[T] ← |id_map|
                enqueue(worklist, T)
            record transition (id_map[S], a, id_map[T])

    accepting ← { id_map[S] | S ∈ id_map, S ∩ nfa.accepting ≠ ∅ }
    return DFA(states=values(id_map), transitions=..., start=0, accepting=accepting)
```

Time complexity: O(2^|Q| × |Σ|) worst case; O(|states_DFA| × |Σ|) typical.  
Space: O(2^|Q|) worst case for the id_map.

### DFA for `(a|b)*abb` — Trace

| DFA State | NFA States | On 'a' | On 'b' | Accepting? |
|-----------|-----------|--------|--------|------------|
| D0 (start) | {0,2,4,6,7,8} | D1 | D2 | No |
| D1 | {0,1,2,4,5,7,8,9,10} | D1 | D3 | No |
| D2 | {0,2,3,4,5,7,8} | D1 | D2 | No |
| D3 | {0,2,3,4,5,7,8,11,12} | D1 | D4 | No |
| D4 | {0,2,3,4,5,7,8,13} | D1 | D2 | **YES** |

Result: **5 states, 10 transitions, 1 accepting state**.  
(NFA had 14 states, 16 transitions → 2.8× reduction)

### Design Decisions

1. **Partial DFA (no explicit dead/trap state)**: Missing transitions are simply
   absent.  `dfa_accepts` treats a missing transition as an implicit reject.
   This keeps small patterns tiny (e.g. `a` → 2 states, not 3).

2. **BFS discovery order**: Guarantees the start state is always ID 0 and
   output is stable across runs.

3. **Sorted alphabet iteration**: Ensures transitions are always added in the
   same order, making `to_dict()` output stable for tests and frontend caching.

4. **Blowup guard**: If `|id_map| ≥ max_states` before adding a new state,
   `DFAConstructionError` is raised immediately.  Default limit: 2,000 states
   (configurable via `SECUREREGEX_MAX_DFA_STATES`).

---

## Phase 6: DFA Minimization (Hopcroft's Algorithm)

**Algorithm chosen: Hopcroft's partition refinement — O(n log n)**  
Selected over the O(n²) table-filling (Myhill-Nerode) approach because:
1. Handles large DFAs from complex char-class patterns efficiently.
2. The industry-standard algorithm; worth documenting academically.
3. Implementation complexity is manageable (~80 lines including dead-state handling).

### Algorithm

```
function hopcroft(dfa):
    dead   ← new_state()          // complete the DFA
    rev    ← precompute_reverse_transitions(dfa ∪ {dead})
    F      ← accepting states
    QF     ← all_states − F (includes dead)
    P      ← {F, QF}              // initial partition
    W      ← {F, QF}              // worklist seeded with both

    while W not empty:
        W ← pop(W)
        for each symbol a:
            X ← {s | ∃ t∈W: delta(s,a) = t}   // via precomputed rev[a]
            for each Y in P:
                if X splits Y (Y∩X ≠ ∅ and Y\X ≠ ∅):
                    replace Y with Y∩X and Y\X
                    if Y in worklist: replace Y with both halves
                    else:            add the smaller half  ← Hopcroft optimisation

    rebuild DFA from live partitions (exclude dead partition)
    renumber: start-block → 0
```

Time: O(|Σ| × n log n) using precomputed reverse transitions.  
Space: O(n) for the partition and worklist sets.

### Two-Phase Process

```
1. BFS unreachable removal   O(|states| + |transitions|)
2. Hopcroft refinement       O(|Σ| × n log n)
```

### `(a|b)*abb` Minimization — Key Insight

| State | NFA set | On 'a' | On 'b' | Accepting? |
|-------|---------|--------|--------|------------|
| D0 | {0,2,4,6,7,8} | D1 | D2 | No |
| D1 | {0,1,2,4,5,7,8,9,10} | D1 | D3 | No |
| **D2** | {0,2,3,4,5,7,8} | **D1** | **D2** | No |
| D3 | {0,2,3,4,5,7,8,11,12} | D1 | D4 | No |
| D4 | {0,2,3,4,5,7,8,13} | D1 | D2 | **Yes** |

**D0 and D2 have identical transitions** (both go to D1 on 'a', to D2 on 'b')
and are both non-accepting. In our **partial DFA** (no explicit dead state)
they are indistinguishable → Hopcroft merges them.

> **Why the Dragon Book says 5 states**: that textbook result uses a *complete*
> DFA with an explicit dead/trap state. In that complete DFA, D0 and D2 differ
> because D0 has no transition on some symbols (going to the dead state) while
> D2 also goes to the dead state — but the dead state is distinguishable from
> all live states, so the merge doesn't happen. Our partial DFA omits the dead
> state entirely, enabling the extra merge.

Minimized 4-state DFA:
```
State 0 (=D0∪D2): ──a──► 1   ──b──► 0 (self-loop)
State 1 (=D1):    ──a──► 1   ──b──► 2
State 2 (=D3):    ──a──► 1   ──b──► 3
State 3 (=D4):    ──a──► 1   ──b──► 0   ← ACCEPTING
```

### Before/After Table (verified by tests)

| Pattern | Original | After Hopcroft | Reduction |
|---------|----------|----------------|-----------|
| `(a|b)*abb` | 5 | **4** | 20.0% |
| `ab\|cb` | 5 | **3** | 40.0% |
| `a` | 2 | 2 | 0.0% |
| `a*` | 1 | 1 | 0.0% |

For `ab|cb`: D1≡D2 (both see only 'b'→accept) and D3≡D4 (both accepting, no outgoing).

---

## Complexity Reference

### Notation

| Symbol | Meaning |
|---|---|
| `n` | length of the regex string |
| `Q_N` | number of NFA states |
| `Q_D` | number of DFA states (before minimization) |
| `|Σ|` | size of the effective alphabet (distinct chars in regex) |
| `m` | length of the test input string |

### Stage-by-stage

| Stage | Time complexity | Space | Notes |
|---|---|---|---|
| Lexer | O(n) | O(n) | Single-pass character scan |
| Parser | O(n) | O(n) | Recursive descent; stack depth ≤ nesting depth |
| Semantic analyser | O(n) | O(1) extra | Single DFS over AST |
| Thompson NFA | O(n) | O(n) | Each AST node → O(1) states + transitions |
| ε-closure | O(Q_N²) worst | O(Q_N) | BFS over ε-edges; runs per DFA state |
| Subset construction | O(2^Q_N × |Σ|) worst | O(2^Q_N) | Exponential worst case; safety cap enforced |
| Hopcroft minimization | O(|Σ| × Q_D log Q_D) | O(Q_D) | Hopcroft 1971 |
| Security analyser | O(n) | O(n) | AST walk + FIRST-set computation |
| DFA simulation | O(m × |Σ|) | O(1) extra | One transition lookup per character |

### Practical behaviour

For typical patterns (n ≤ 100, |Σ| ≤ 26):

- NFA states ≈ 2n (Thompson doubles states per construction step)
- DFA states ≈ O(n²) in practice; rarely hits the exponential worst case
- Minimized DFA ≤ DFA always (guaranteed by Hopcroft)
- Full pipeline end-to-end: < 5 ms for patterns up to 200 characters

The safety cap (`max_dfa_states = 2000`) prevents subset-construction blowup
from hanging the server, returning a structured `DFAConstructionError` instead.

---

## Implementation Summary

| Component | Source module | Algorithm | Complexity |
|---|---|---|---|
| Tokeniser | `app/lexer/tokeniser.py` | Single-pass scan | O(n) |
| Parser | `app/parser/parser.py` | Recursive descent | O(n) |
| AST | `app/ast/nodes.py` | Immutable hierarchy | — |
| Semantic | `app/semantic/analyser.py` | DFS tree walk | O(n) |
| NFA | `app/nfa/builder.py` | Thompson's construction | O(n) |
| DFA | `app/dfa/builder.py` | Subset construction | O(2^n) worst / O(n²) typical |
| Minimizer | `app/optimizer/minimizer.py` | Hopcroft's algorithm | O(|Σ| n log n) |
| Security | `app/security/analyser.py` | AST heuristics | O(n) |

All modules are covered by automated tests. See [`docs/testing.md`](testing.md) for the
complete test inventory and [`examples/fixtures.json`](../examples/fixtures.json) for the
validated regex battery.
