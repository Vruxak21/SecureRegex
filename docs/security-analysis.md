# SecureRegex — Security Analysis Reference

## Overview

SecureRegex's Security Analyzer walks the parsed Abstract Syntax Tree (AST)
and applies **heuristic structural rules** to detect patterns associated with
**ReDoS (Regular Expression Denial of Service)** in backtracking-based regex
engines.

> **Important caveat**: SecureRegex's *own* DFA-based evaluation engine does
> **not backtrack** and is therefore **immune to ReDoS** by construction.
> Every finding is a potential risk indicator for environments where the same
> pattern is executed by a *backtracking* engine (Python `re`, JavaScript,
> Java `java.util.regex`, .NET, PCRE, Perl, Ruby, etc.).  Findings should be
> treated as *potential risk*, never as confirmed vulnerabilities.

---

## Background: Why Backtracking Engines Are Vulnerable

A backtracking NFA-based regex engine resolves ambiguity by exploring all
possible match paths recursively.  When a pattern contains **nested or
overlapping repetition**, the number of paths can grow **exponentially** with
input length.

Classic example — `(a+)+` on input `"aaaaaX"`:

```
Iteration  Partitions tried
    1       (aaaaa) → fails on X
    2       (aaaa)(a) → fails on X
            (aaa)(aa) → …
            (aa)(aaa) → …
            (a)(aaaa) → …
    3       (aaa)(a)(a), (aa)(aa)(a), … → …
    …       exponentially many splits
```

Total attempts: O(2^n) — the engine hangs for inputs of moderate length.

---

## Rule Definitions

### SEC001 — Nested Quantifiers (HIGH)

**Trigger**: A `*` or `+` quantifier whose child sub-tree contains another `*`
or `+`.

```
(a+)+     ← outer + wraps inner +
(a*)*     ← outer * wraps inner *
([a-z]+)+ ← char-class + under outer +
((ab)+)+  ← group containing + under outer +
```

**Why it is dangerous**: The inner loop and the outer loop compete for the same
characters.  For an input of `n` matching characters followed by a failure
character, the engine can split the characters among the two loops in O(2^n)
ways.

**Recommendation**: Collapse the nesting.  `(a+)+` → `a+`.  Use possessive
quantifiers (`(a++)` in Java/PCRE) or atomic groups (`(?>a+)`) if the engine
supports them.

**False-positive analysis**: Some nested patterns are less catastrophic in
practice:
- `(a+b)+` — inner `+` matches only `a`, outer boundary is forced by mandatory
  `b`.  Backtracking is O(n²) (polynomial), not exponential.  This is still
  flagged at HIGH as a **conservative** measure because the structural
  pattern is indistinguishable from truly catastrophic patterns without
  deeper semantic analysis.

---

### SEC002 — Overlapping Alternation in Repetition (HIGH or MEDIUM)

**Trigger**: A `*` or `+` wrapping a `|` alternation where at least two
branches share one or more first characters (`FIRST(X) ∩ FIRST(Y) ≠ ∅`).

**Severity**:
- **HIGH** — when one branch's language is a prefix of another's (the engine
  cannot determine at which iteration to commit to a split).
- **MEDIUM** — first-character overlap without a clear prefix relationship
  (possible but less certain backtracking risk).

```
(a|aa)+   ← HIGH: 'a' is a prefix of 'aa'
(a|a+b)+  ← HIGH: 'a' can extend to 'a+b'
(ab|ac)+  ← MEDIUM: share first char 'a', but 'b'/'c' disambiguate
```

**Why it is dangerous**: For `(a|aa)+` on `"aaaaaX"`, the engine can choose
the `a` branch or the `aa` branch at each iteration.  The number of ways to
partition `n` 'a' characters grows exponentially.

**Recommendation**: Make branches mutually exclusive from the first character.
Replace `(a|aa)+` with `a+` if that captures the intent.  Use a character
class `[ab]` instead of `(a|b)` where possible.

**False-positive analysis**:
- `(ab|ac)+` — the second character ('b' vs 'c') fully disambiguates the
  branch after the shared 'a'.  **Backtracking is O(n), not exponential.**
  This is a **known false positive** at MEDIUM severity.  It is flagged to
  alert the author to review the pattern, but is unlikely to be exploitable.
- `(a|b)*` — `FIRST('a') ∩ FIRST('b') = ∅`, so this is **not flagged**.

---

### SEC003 — Repetition Over Nullable Expression (MEDIUM)

**Trigger**: A `*` or `+` whose child can match the **empty string (ε)** and
is not a plain `ε` node.

```
(a?)+   ← a? is nullable; outer + can loop on zero-width matches
(a|ε)*  ← union branch is ε
```

**Why it is dangerous**: Some backtracking engines enter an **infinite loop**
when the inner pattern matches ε on every iteration (zero-width match loop).
Most modern engines detect this and bail out, but the behaviour is
engine-specific.

**Recommendation**: Ensure the repeated expression always consumes at least one
character.  `(a?)+` → `a*`.  If the nullable inner is intentional, test
carefully across all target engines.

**Note**: When SEC001 fires for the same quantifier (e.g. `(a*)+` — inner
`*` under outer `+`), SEC003 is suppressed to avoid duplicate findings.

---

## First-Character Computation (`FIRST`)

The `FIRST(node)` function returns all characters that can appear as the first
consumed character of any string matched by `node`:

| Node type | `FIRST(node)` |
|-----------|--------------|
| `Literal(c)` | `{c}` |
| `CharClass([a-z])` | `{'a', 'b', …, 'z'}` |
| `Concat(L, R)` | `FIRST(L) ∪ FIRST(R)` if `L` is nullable, else `FIRST(L)` |
| `Union(L, R)` | `FIRST(L) ∪ FIRST(R)` |
| `Star(X)` / `Question(X)` | `FIRST(X)` |
| `Plus(X)` | `FIRST(X)` |
| `Epsilon` | `∅` |
| `Dot` | all printable ASCII |

---

## Language-Prefix Detection

For SEC002 severity classification, `_is_language_prefix(shorter, longer)`
returns `True` when L(shorter) contains a string that is a proper prefix of
some string in L(longer).  The heuristic cases:

1. `shorter` is nullable → `True` (ε is prefix of everything)
2. Both are `LiteralNode` with the same character → `True`
3. `shorter` is a `LiteralNode(c)` and `longer = Concat(LiteralNode(c), …)` → `True`
4. `shorter` is a `LiteralNode(c)` and `longer` is `Star/Plus(…)` starting with `c` → `True`

All other cases return `False` conservatively.

---

## Known Limitations / False Negatives

Some dangerous patterns are **not detected** by the current heuristics:

| Pattern | Risk | Reason not flagged |
|---------|------|--------------------|
| `(a\|b\|c)+` where L(a) ⊂ L(b) | HIGH | Multi-branch prefix not fully checked |
| `a{2,10}` equivalent patterns | Varies | Counted repetition not in v1 syntax |
| Indirect mutual recursion | HIGH | Requires full language-inclusion testing |
| `(\w+\s)+` on long lines | HIGH | `\w` shorthand not in v1 syntax |

These limitations are documented here; future versions may apply automata-based
language-inclusion testing for higher precision.

---

## Output Format

Every `SecurityReport` contains:

```json
{
  "overall_risk": "HIGH | MEDIUM | LOW | NONE",
  "findings": [
    {
      "rule_id":        "SEC001",
      "risk_level":     "HIGH",
      "title":          "Nested Quantifiers",
      "reason":         "A '+' quantifier wraps ... a '*' or '+' ...",
      "explanation":    "Nested repetition causes catastrophic backtracking ...",
      "recommendation": "Eliminate the nesting ...",
      "location":       {"start": 5, "end": 5}
    }
  ],
  "caveat": "Findings are heuristic risk indicators only. ..."
}
```

`location.start` and `location.end` are **1-indexed column numbers** in the
original regex string, pointing to the triggering quantifier token.

---

## Example Reports

### `(a+)+` — HIGH risk (SEC001)

```json
{
  "overall_risk": "HIGH",
  "findings": [{
    "rule_id":        "SEC001",
    "risk_level":     "HIGH",
    "title":          "Nested Quantifiers",
    "reason":         "A '+' quantifier wraps an expression that itself contains a '*' or '+' repetition.",
    "explanation":    "Nested repetition ... exponentially many ways ... 'aaa...aX'.",
    "recommendation": "Eliminate the nesting. '(a+)+' simplifies to 'a+'...",
    "location":       {"start": 5, "end": 5}
  }],
  "caveat": "Findings are heuristic risk indicators only. ..."
}
```

### `(a|b)*abb` — NONE (safe)

```json
{
  "overall_risk": "NONE",
  "findings": [],
  "caveat": "Findings are heuristic risk indicators only. ..."
}
```

Reason: `(a|b)*` — FIRST('a') ∩ FIRST('b') = ∅, so SEC002 does not fire.
The `*` wraps a Union with no inner Star/Plus, so SEC001 does not fire.
