# SecureRegex — Architecture

## System Overview

SecureRegex is a full-stack web application with a Python/FastAPI backend compiler
pipeline and a React/TypeScript frontend visualizer. The two tiers communicate over
a single REST API.

---

## Pipeline Diagram

```
 User (browser)
     │
     │  HTTP POST /api/v1/analyze { "regex": "..." }
     ▼
 ┌─────────────────────────────────────────────────────────────┐
 │                    FastAPI Backend                           │
 │                                                             │
 │  ① Input Validation ─────── RegexTooLongError (422)        │
 │         │                                                   │
 │  ② Lexer ────────────────── LexerError (400)               │
 │         │ Token[]                                           │
 │  ③ Parser ───────────────── ParseError (400)               │
 │         │ ASTNode                                           │
 │  ④ Semantic Analyser ─────  list[Diagnostic]               │
 │         │ Validated AST   ERROR severity → stop pipeline   │
 │  ⑤ Thompson NFA ──────────  NFA (states, ε-transitions)    │
 │         │ NFA                                               │
 │  ⑥ Subset Construction ───  DFA (deterministic)            │
 │         │ DFA              DFAConstructionError if > cap   │
 │  ⑦ Hopcroft Minimization ─  DFA_min + MinimizationStats    │
 │         │ min_DFA                                           │
 │  ⑧ Security Analyser ─────  SecurityReport                 │
 │         │                                                   │
 │  ⑨ Assemble Response ────── AnalyzeResponse (Pydantic)     │
 └─────────────────────────────────────────────────────────────┘
     │
     │  JSON (tokens, ast, nfa, dfa, minimized_dfa,
     │        diagnostics, security, stats)
     ▼
 ┌─────────────────────────────────────────────────────────────┐
 │                 React/TypeScript Frontend                    │
 │                                                             │
 │  HomePage                                                   │
 │  ├── Regex input + example buttons                         │
 │  ├── Error banner (structured lexer/parser/semantic errs)  │
 │  └── ResultsDashboard                                       │
 │       ├── Tab: Tokens      → TokensTab  (type/value table) │
 │       ├── Tab: AST         → ASTTab     (recursive tree)   │
 │       ├── Tab: NFA    ─┐                                   │
 │       ├── Tab: DFA     ├── AutomataTab                     │
 │       ├── Tab: Min DFA ─┘  (React Flow graph / table)      │
 │       ├── Tab: Security    → SecurityTab  (risk + findings)│
 │       ├── Tab: Test Regex  → TestRegexTab                  │
 │       │         (step-through DFA traversal on graph)      │
 │       └── Sidebar: StatsPanel (10 pipeline statistics)     │
 └─────────────────────────────────────────────────────────────┘
```

---

## Component Responsibilities

### Backend — `backend/app/`

| Module | File(s) | Responsibility |
|---|---|---|
| **Lexer** | `lexer/tokeniser.py` | Convert raw regex string → `Token[]`. Recognises all metacharacters, char-class syntax, escape sequences. Raises `LexerError` on unrecognised constructs. |
| **Parser** | `parser/parser.py` | Recursive-descent parser consuming the token stream → `ASTNode`. Implements EBNF grammar with correct precedence (quantifier > concat > alternation). Raises `ParseError` for syntax violations. |
| **AST** | `ast/nodes.py` | Immutable node hierarchy: `LiteralNode`, `ConcatNode`, `UnionNode`, `StarNode`, `PlusNode`, `QuestionNode`, `EpsilonNode`, `CharClassNode`. All nodes expose `to_dict()` for JSON serialization. |
| **Semantic Analyser** | `semantic/analyser.py` | Single-pass AST walker producing `list[Diagnostic]`. Rules: SEM001 (invalid char range), SEM002 (redundant quantifier), SEM003 (unsupported dot). Never raises exceptions. |
| **NFA** | `nfa/builder.py` | Thompson's construction: each AST node type → NFA fragment with one start + one accepting state. Fragments composed bottom-up. All states have globally unique integer IDs. |
| **DFA** | `dfa/builder.py` | Subset construction (powers-of-set). Computes ε-closure, BFS over state sets. Effective alphabet derived from the regex's literals (not full Unicode). Enforces `max_dfa_states` cap. |
| **Optimizer** | `optimizer/minimizer.py` | Hopcroft's partition-refinement algorithm. First removes unreachable states, then splits equivalence classes until stable. Returns a new `DFA` + `MinimizationStats`. |
| **Security** | `security/analyser.py` | AST structural heuristics: SEC001 (nested quantifiers), SEC002 (overlapping alternation), SEC003 (nullable repetition). Returns `SecurityReport` with per-finding structured output. |
| **API** | `api/pipeline.py`, `api/router.py`, `api/models.py` | Orchestrates all stages. Catches all `SecureRegexError` subclasses and converts them to structured JSON. Provides `/analyze` and `/test` endpoints plus `/health` and `/api/v1/info`. |
| **Config** | `config.py` | `pydantic-settings` `Settings` class. All limits and CORS origins are environment-variable overrideable. Singleton imported everywhere. |
| **Exceptions** | `exceptions.py` | `SecureRegexError` hierarchy: `LexerError`, `ParseError`, `SemanticError`, `DFAConstructionError`, `RegexTooLongError`, `InputTooLongError`, `SimulationTimeoutError`. Each carries an HTTP status code and structured `to_dict()`. |

### Frontend — `frontend/src/`

| Module | File(s) | Responsibility |
|---|---|---|
| **API client** | `api/client.ts` | Typed `post()` helper wrapping `fetch`. `api.analyze(regex)` and `api.test(regex, input)`. `extractErrorMessage()` converts backend error JSON to UI string. |
| **Types** | `types/api.ts` | TypeScript interfaces mirroring all Pydantic models: `Token`, `ASTNode`, `Automaton`, `AutomataTransition`, `SecurityFinding`, `SecurityReport`, `PipelineStats`, `AnalyzeResponse`, `TestResponse`, `ApiError`. |
| **HomePage** | `pages/HomePage.tsx` | Main controller: regex input, example pattern buttons, error banner (with column indicator), Analyze/Clear buttons, backend health polling, `ResultsDashboard` rendering. |
| **ResultsDashboard** | `components/ResultsDashboard.tsx` | 7-tab layout (shadcn-style) + `StatsPanel` sidebar. Owns no data — all props-in from `HomePage`. |
| **TokensTab** | `components/TokensTab.tsx` | Renders `Token[]` as a colour-coded table (type badge, value, column). |
| **ASTTab** | `components/ASTTab.tsx` | Recursive indented tree renderer. Each node type has a distinct icon/colour. |
| **AutomataTab** | `components/AutomataTab.tsx` | NFA / DFA / Min DFA sub-tabs with Graph ↔ Table toggle. Delegates graph to `AutomataGraph`. |
| **SecurityTab** | `components/SecurityTab.tsx` | Overall risk banner, per-finding cards with expandable explanation, and always-visible disclaimer caveat. |
| **TestRegexTab** | `components/TestRegexTab.tsx` | Input + Test button → `/api/test`. Displays match/reject badge, interactive step-through traversal with ⏮◀▶⏭ controls, highlighted DFA graph, and clickable path strip. |
| **StatsPanel** | `components/StatsPanel.tsx` | 10-metric sidebar: regex length, token count, AST nodes, NFA states/transitions, DFA states/transitions, minimized DFA states, reduction %, risk level. |
| **AutomataGraph** | `visualizations/AutomataGraph.tsx` | React Flow canvas with zoom/pan, dot-grid background, `Controls`. Click-to-inspect floating panel shows outgoing/incoming transitions. |
| **AutomataStateNode** | `visualizations/AutomataStateNode.tsx` | Custom RF node: circular shape, accepting double-ring, start `→` arrow indicator, highlighted glow for traversal. |
| **automataToFlow** | `visualizations/automataToFlow.ts` | Pure conversion utility: `Automaton → {nodes, edges}`. Circular layout (start at 9 o'clock). Parallel edge merging. `highlightedStates[]` → `isHighlighted` flag. |

---

## Key Design Decisions

### No `re` module
The Python standard-library `re` module is explicitly excluded from all core pipeline
modules. Every stage is implemented from first principles. This is enforced by code
review and grep-checked in CI.

### Pydantic settings
All configuration lives in `app/config.py` using `pydantic-settings`. Environment-variable
overrides require no code changes — critical for Docker/CI deployment.

### Structured errors, never raw tracebacks
Every domain error is a subclass of `SecureRegexError`. A single FastAPI exception
handler catches these and returns:
```json
{ "error": "PARSE_ERROR", "message": "...", "position": { "line": 1, "column": N } }
```
Raw Python tracebacks never reach the HTTP client (verified by 1097 automated tests).

### Safety caps
`max_nfa_states` (5000), `max_dfa_states` (2000), and `max_computation_steps` (1,000,000)
prevent pathological inputs from hanging the server. Each limit is checked at the correct
pipeline stage and returns a structured `DFAConstructionError` or `SimulationTimeoutError`.

### Effective alphabet
The DFA subset construction uses only the characters actually appearing in the regex
(literals + character-class ranges), not the full Unicode alphabet. This keeps the
state-space tractable for typical patterns.

### Security findings are heuristic only
Every `SecurityReport` includes a mandatory `caveat` field explaining that findings are
structural risk indicators for backtracking engines. SecureRegex's own DFA engine does
not backtrack and is immune to ReDoS. The caveat is tested in the automated suite.

---

## Data Flow: `/api/v1/test`

```
POST /api/v1/test { "regex": "(a|b)*abb", "input": "abb" }
     │
     ├─ Re-runs stages ①–⑦ (or uses cached result if same regex)
     │
     ├─ DFA simulation: ε-closure + BFS through minimized DFA
     │    state 0 ─(a)─▶ state 1 ─(b)─▶ state 3 ─(b)─▶ state 4★
     │
     └─▶ { "matched": true, "path": [0, 1, 3, 4] }
```

The `path` is used by the frontend's step-through traversal to highlight states
one at a time as the user steps through the input with the ⏮◀▶⏭ controls.

---

## Deployment

### Docker (production-ready)

```
docker-compose up --build
```

- Backend: `python:3.12-slim` base, `uvicorn` server
- Frontend: `node:20-slim` base, `vite` dev server (for demo; use `nginx` in production)
- Health-check: backend must pass before frontend starts (`depends_on.condition: service_healthy`)

### Local (development)

See [README.md](../README.md#quick-start) for step-by-step instructions.
