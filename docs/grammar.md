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

---

## Token Reference

| Token type | Lexeme | Context |
|---|---|---|
| `CHAR` | any non-metacharacter, or any character inside `[…]` | everywhere |
| `LPAREN` | `(` | outside char class |
| `RPAREN` | `)` | outside char class |
| `OR` | `\|` | outside char class |
| `STAR` | `*` | outside char class |
| `PLUS` | `+` | outside char class |
| `QUESTION` | `?` | outside char class |
| `LBRACKET` | `[` | starts char class |
| `RBRACKET` | `]` | ends char class |
| `DASH` | `-` | inside char class only |
| `CARET` | `^` | immediately after `[` |
| `DOT` | `.` | outside char class |
| `EOF` | (end of input) | — |

All characters that are metacharacters *outside* a character class (`( ) | * + ? [ . ^`) are
treated as literal `CHAR` tokens *inside* a character class, except `]` (which closes it)
and `-` (which is `DASH`). The lexer is context-sensitive on `[…]` boundaries.

---

## Grammar Ambiguity Notes

The grammar as written is **unambiguous** given the precedence rules:

1. **Quantifiers bind tightest** — they always apply to the immediately preceding primary.
   There is no ambiguity in `a*b+` (Star(a) then Plus(b)).

2. **Concatenation is explicit in the grammar** via the `{ repetition }` kleene-star on the
   `concatenation` rule. The parser never needs to insert invisible concat operators.

3. **Alternation `|` has lowest precedence** — `a|bc` = `Union(a, Concat(b,c))` without
   any ambiguity.

4. **Parentheses reset precedence** — `(a|b)*` is unambiguous: `Star(Union(a,b))`.

The only intentional quirk: consecutive quantifiers (`a**`) are *syntactically accepted*
(each quantifier applies to the result of the previous one) but flagged as SEM002 WARNING
because the outer quantifier is almost always a typo.

---

## Complete Parse Error Catalogue

| Input | Error type | Message |
|---|---|---|
| `(` | ParseError | Missing closing ')' at column 1 |
| `(ab` | ParseError | Missing closing ')' for '(' at column 1 |
| `)` | ParseError | Unexpected token ')' at column 1 |
| `a)` | ParseError | Unexpected token ')' at column 2 |
| `()` | ParseError | Empty group '()' at column 1 |
| `\|` | ParseError | Expected expression before '\|' at column 1 |
| `a\|` | ParseError | Expected expression after '\|' at column 2 |
| `a\|\|b` | ParseError | Expected expression after '\|' at column 3 |
| `*` | ParseError | Quantifier '*' at column 1 has nothing to quantify |
| `+` | ParseError | Quantifier '+' at column 1 has nothing to quantify |
| `?` | ParseError | Quantifier '?' at column 1 has nothing to quantify |
| `[` | ParseError | Unclosed character class '[' at column 1 |
| `[a-z` | ParseError | Unclosed character class '[' at column 1 |
| `[]` | ParseError | Empty character class at column 1 |

Semantic errors (returned in `diagnostics[]`, not as exceptions):

| Input | Code | Severity | Message |
|---|---|---|---|
| `[z-a]` | SEM001 | ERROR | Invalid character class range 'z-a' |
| `a**` | SEM002 | WARNING | Redundant consecutive quantifier |
| `a.b` | SEM003 | ERROR | Dot wildcard not supported in v1 |
