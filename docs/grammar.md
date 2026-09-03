# SecureRegex v1 — Formal Grammar

## EBNF Notation

```ebnf
(* ─────────────────────────────────────────────────────────────────────────── *)
(*  SecureRegex v1 — Extended Backus–Naur Form                                 *)
(*                                                                             *)
(*  Terminals (token types from the Lexer)                                     *)
(*    CHAR      – any literal character (including resolved escape sequences)  *)
(*    DOT       – the '.' wildcard                                             *)
(*    LPAREN    – '('                                                           *)
(*    RPAREN    – ')'                                                           *)
(*    OR        – '|'                                                           *)
(*    STAR      – '*'                                                           *)
(*    PLUS      – '+'                                                           *)
(*    QUESTION  – '?'                                                           *)
(*    LBRACKET  – '['                                                           *)
(*    RBRACKET  – ']'                                                           *)
(*    DASH      – '-'  (only inside character classes)                         *)
(*    CARET     – '^'  (only inside character classes)                         *)
(*    EOF       – end of token stream                                           *)
(* ─────────────────────────────────────────────────────────────────────────── *)

regex        = alternation , EOF ;

alternation  = concatenation , { OR , concatenation } ;

concatenation = repetition , { repetition } ;

repetition   = primary , [ quantifier ] ;

quantifier   = STAR | PLUS | QUESTION ;

primary      = LPAREN , alternation , RPAREN
             | char_class
             | CHAR
             | DOT
             ;

char_class   = LBRACKET , [ CARET ] , class_body , RBRACKET ;

class_body   = class_item , { class_item } ;

class_item   = CHAR , [ DASH , CHAR ]
             | DASH                     (* literal '-' at start or end *)
             ;
```

---

## Operator Precedence (tightest → loosest)

| Level | Operator | Associativity | Example |
|-------|----------|---------------|---------|
| 1 (tightest) | `*` `+` `?` — quantifiers | Postfix, left | `a**` = `Star(Star(a))` |
| 2 | Concatenation (implicit) | Left | `abc` = `Concat(Concat(a,b),c)` |
| 3 (loosest) | `\|` — alternation | Left | `a\|b\|c` = `Union(Union(a,b),c)` |

Grouping with `(…)` overrides precedence at any level.

---

## Well-Formedness Constraints

Constraints enforced at **parse time** (raise `ParseError`):

| Constraint | Example violation | Error message |
|------------|-------------------|---------------|
| Empty group | `()` | "Empty group '()' at column N" |
| Unmatched `(` | `(a|b` | "Missing closing ')' for '(' at column N" |
| Unmatched `)` | `a|b)` | "Unexpected token ')' at column N" |
| Dangling `\|` (right) | `a\|` | "Expected an expression after '|' at column N" |
| Bare quantifier | `*a`, `+b` | "Quantifier '*' at column N has nothing to quantify" |
| Unclosed `[` | `[a-z` | "Unclosed character class '[' at column N" |
| Empty class | `[]` | "Empty character class at column N" |
| Inverted range | `[z-a]` | "Invalid character range 'z-a' at column N" |

Constraints deferred to **semantic analysis** (Phase 3):

- Dot `.` wildcard (not in v1 supported syntax — lexed, then rejected)
- `\d`, `\w`, `\s` shorthand classes (similarly lexed then rejected)
- Consecutive quantifiers `a**` (flagged as suspicious)

---

## Example Parse Trees

### `(a|b)*abb`

```
Concat
├── Concat
│   ├── Concat
│   │   ├── Star
│   │   │   └── Union
│   │   │       ├── Literal('a')
│   │   │       └── Literal('b')
│   │   └── Literal('a')
│   └── Literal('b')
└── Literal('b')
```

### `[a-z]+`

```
Plus
└── CharClass(negate=False, ranges=[ClassRange('a','z')])
```

### `(ab)+|[0-9]*`

```
Union
├── Plus
│   └── Concat
│       ├── Literal('a')
│       └── Literal('b')
└── Star
    └── CharClass(negate=False, ranges=[ClassRange('0','9')])
```

---

## Out of Scope (v1)

The following are **lexed** but will be **rejected by the semantic analyser**:

- `.` wildcard (DotNode)
- `\d` `\w` `\s` shorthand character classes
- Negated character classes `[^…]` (CARET token — lexed, deferred)

The following are **completely out of scope** and will be caught at the lexer level:

- Lookahead / lookbehind `(?=…)` `(?!…)` `(?<=…)` `(?<!…)`
- Non-capturing / named groups `(?:…)` `(?P<name>…)`
- Backreferences `\1`
- Conditionals `(?(id)yes|no)`
- POSIX bracket expressions `[:alpha:]`
