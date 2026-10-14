# SecureRegex

> **Compiler-based Regular Expression Security Analyzer and Automata Visualizer**  
> A fully hand-written compiler pipeline: Lexer → Parser → AST → Semantic Analyzer → Thompson NFA → Subset-Construction DFA → Hopcroft Minimization → ReDoS Security Analyzer, with an interactive React Flow visualization dashboard.

[![Python](https://img.shields.io/badge/Python-3.12+-blue?logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green?logo=fastapi)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18+-61DAFB?logo=react)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.5+-3178C6?logo=typescript)](https://typescriptlang.org)
[![Tests](https://img.shields.io/badge/tests-1220%20passed-brightgreen)](#running-tests)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

---

## What is SecureRegex?

SecureRegex analyses regular expressions end-to-end:

1. **Compiler pipeline** — a pure hand-written Lexer → Parser → NFA → DFA → Minimizer.  
   No Python `re`, no third-party regex library is used for the core engine.
2. **Security analysis** — structural ReDoS heuristics (SEC001/SEC002/SEC003)  
   detecting nested quantifiers, overlapping alternation, and nullable repetition.
3. **Interactive visualizer** — React Flow graph of NFA, DFA, and Minimized DFA  
   with click-to-inspect, zoom/pan, and step-through DFA traversal for a test string.

---

## Screenshots

```
┌─────────────────────────────────────────────────────────────┐
│  SecureRegex  v0.1.0  ● Backend online         [API Docs]   │
├─────────────────────────────────────────────────────────────┤
│  Regex:  [(a|b)*abb________________]  [Analyze] [Clear]     │
│                                                             │
│  ┌──Tokens──┬──AST──┬──NFA──┬──DFA──┬──Min──┬──Security──┐  │
│  │                                                       │  │
│  │   ⬡ Graph / ≡ Table toggle                            │  │
│  │                                                       │  │
│  │   q0(→) ──a──▶ q1 ──b──▶ q3 ──b──▶ q4★                │  │
│  │    │          ↑                                       │  │
│  │    └──b──▶ q2─┘                                       │  │
│  │                                                       │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                             │
│  Stats: NFA 14st · DFA 5st · Min 4st · Reduction 20%        │
│         Security: NONE                                      │
└─────────────────────────────────────────────────────────────┘
```

> Full browser screenshots are in [`docs/screenshots/`](docs/screenshots/) (add after first run).

---

## Architecture

```
Regex string  (HTTP POST /api/v1/analyze)
      │
      ▼
 ┌──────────┐
 │  Lexer   │  Hand-written DFA tokeniser → 18 token types
 │ app/lexer│  (CHAR, STAR, PLUS, QUESTION, OR, LPAREN, RPAREN,
 └────┬─────┘   LBRACKET, RBRACKET, DASH, CARET, DOT, EOF, …)
      │ Token[]
      ▼
 ┌──────────┐
 │  Parser  │  Recursive-descent; implements EBNF grammar
 │app/parser│  Precedence: quantifier > concat > alternation
 └────┬─────┘
      │ ASTNode
      ▼
 ┌──────────┐
 │ Semantic │  AST walk → list[Diagnostic]
 │ Analyser │  SEM001 (bad range) · SEM002 (redundant quant)
 │app/semant│  SEM003 (unsupported dot wildcard)
 └────┬─────┘
      │ Validated AST
      ▼
 ┌──────────┐
 │ Thompson │  Per-node ε-NFA fragments, composed recursively
 │   NFA    │  literal · concat · union · star · plus · question
 │  app/nfa │  · epsilon · char-class
 └────┬─────┘
      │ NFA (states, ε-transitions, start, accepting)
      ▼
 ┌──────────┐
 │  Subset  │  ε-closure + BFS; effective alphabet from literals
 │Constructn│  Safety cap: max_dfa_states (default 2000)
 │  app/dfa │
 └────┬─────┘
      │ DFA (deterministic, no ε)
      ▼
 ┌──────────┐
 │ Hopcroft │  Partition-refinement minimization
 │   Min    │  Removes unreachable states first
 │app/optim.│  Returns reduction % statistics
 └────┬─────┘
      │ Minimized DFA
      ▼
 ┌──────────┐
 │ Security │  AST structural heuristics
 │ Analyser │  SEC001 · SEC002 · SEC003
 │app/securi│  Risk: NONE/LOW/MEDIUM/HIGH
 └────┬─────┘
      │ SecurityReport
      ▼
 ┌──────────┐
 │ FastAPI  │  POST /api/v1/analyze → full JSON report
 │   API    │  POST /api/v1/test   → matched + DFA path
 │  app/api │  GET  /health        → liveness
 └────┬─────┘
      │ JSON
      ▼
 ┌──────────────────────────────┐
 │  React + TypeScript Frontend │
 │  7-tab results dashboard     │
 │  React Flow automata graphs  │
 │  Step-through DFA traversal  │
 └──────────────────────────────┘
```

---

## Project Structure

```
secureregex/
├── backend/
│   ├── app/
│   │   ├── lexer/          # Tokeniser — 18 token types
│   │   ├── parser/         # Recursive-descent parser → AST
│   │   ├── ast/            # ASTNode hierarchy
│   │   ├── semantic/       # SEM001–SEM003 diagnostics
│   │   ├── nfa/            # Thompson's construction
│   │   ├── dfa/            # Subset construction + simulation
│   │   ├── optimizer/      # Hopcroft DFA minimization
│   │   ├── security/       # ReDoS heuristics (SEC001–SEC003)
│   │   ├── api/            # FastAPI routers + Pydantic models
│   │   ├── config.py       # Pydantic-settings (env vars)
│   │   ├── exceptions.py   # SecureRegexError hierarchy
│   │   └── main.py         # ASGI app entry-point
│   ├── tests/              # 11 pytest test files — 1097 tests
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── api/            # Typed fetch client (api.analyze, api.test)
│   │   ├── components/     # TokensTab, ASTTab, AutomataTab, SecurityTab,
│   │   │                   # TestRegexTab, StatsPanel, ResultsDashboard
│   │   ├── pages/          # HomePage (main entry point)
│   │   ├── visualizations/ # AutomataGraph, AutomataStateNode, automataToFlow
│   │   └── types/          # TypeScript mirrors of Pydantic models
│   ├── tests/              # 4 Vitest test files — 123 tests
│   ├── vite.config.ts
│   └── Dockerfile
├── docs/
│   ├── architecture.md     # System diagram + component responsibilities
│   ├── algorithms.md       # Thompson, subset construction, Hopcroft + complexity
│   ├── grammar.md          # EBNF grammar + precedence table
│   ├── security-analysis.md # SEC001–SEC003 heuristics, caveats, false positives
│   └── testing.md          # Test inventory + manual verification checklist
├── examples/
│   └── fixtures.json       # 13-pattern battery (7 safe + 6 risky)
├── docker-compose.yml
├── LICENSE
└── README.md
```

---

## Quick Start

### Option A — Docker (recommended)

> Requires: [Docker Desktop](https://www.docker.com/products/docker-desktop/)

```bash
git clone https://github.com/Vruxak21/SecureRegex.git
cd SecureRegex
docker-compose up --build
```

| Service | URL |
|---|---|
| Frontend | http://localhost:5173 |
| Backend API | http://localhost:8000 |
| Swagger docs | http://localhost:8000/docs |
| Health check | http://localhost:8000/health |

### Option B — Local development

#### Backend

> Requires: Python 3.12+ (tested on 3.14)

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install -r requirements.txt -r requirements-dev.txt
# Python 3.14 on macOS arm64 (binary-only):
# pip install --only-binary=:all: -r requirements.txt -r requirements-dev.txt

uvicorn app.main:app --reload --port 8000
```

#### Frontend

> Requires: Node.js 20+

```bash
cd frontend
npm install --legacy-peer-deps
npm run dev
# Open http://localhost:5173
```

---

## Running Tests

### Backend (pytest) — 1097 tests

```bash
cd backend
source .venv/bin/activate

pytest                         # all tests, short traceback
pytest -v                      # verbose
pytest tests/test_e2e.py -v   # Phase 11 E2E battery only
pytest tests/test_security.py  # security analyzer only
```

Expected output:
```
========================= 1097 passed in 0.76s =========================
```

### Frontend (Vitest) — 123 tests

```bash
cd frontend
npm test                       # single pass
npx vitest --watch             # watch mode
npx vitest tests/Phase11.test.tsx  # E2E smoke only
```

Expected output:
```
Test Files  4 passed (4)
     Tests  123 passed (123)  Duration 1.39s
```

---

## API Reference

### `POST /api/v1/analyze`

**Request**
```json
{ "regex": "(a|b)*abb" }
```

**Response** (abridged)
```json
{
  "success": true,
  "tokens":  [...],
  "ast":     {...},
  "nfa":     { "states": [...], "transitions": [...], "start": 6, "accepting": [13] },
  "dfa":     { "states": [...], "transitions": [...], "start": 0, "accepting": [4]  },
  "minimized_dfa": { "states": [...], "start": 0, "accepting": [3] },
  "diagnostics": [],
  "security": {
    "overall_risk": "NONE",
    "findings": [],
    "caveat": "Findings are heuristic risk indicators only..."
  },
  "stats": {
    "nfa_states": 14, "dfa_states": 5,
    "minimized_dfa_states": 4, "dfa_reduction_pct": 20.0,
    "overall_security_risk": "NONE"
  }
}
```

### `POST /api/v1/test`

**Request**
```json
{ "regex": "(a|b)*abb", "input": "abb" }
```

**Response**
```json
{ "matched": true, "path": [0, 1, 3, 4] }
```

---

## Configuration

All settings are environment variables prefixed `SECUREREGEX_`:

| Variable | Default | Description |
|---|---|---|
| `SECUREREGEX_DEBUG` | `false` | Enable debug logging |
| `SECUREREGEX_MAX_REGEX_LENGTH` | `1000` | Max regex pattern characters |
| `SECUREREGEX_MAX_INPUT_LENGTH` | `10000` | Max test-string characters |
| `SECUREREGEX_MAX_NFA_STATES` | `5000` | NFA state cap (safety) |
| `SECUREREGEX_MAX_DFA_STATES` | `2000` | DFA state cap (prevents blowup) |
| `SECUREREGEX_MAX_COMPUTATION_STEPS` | `1000000` | Simulation step limit |
| `SECUREREGEX_CORS_ORIGINS` | `["http://localhost:5173"]` | Allowed CORS origins |

---

## Security Findings Reference

| Rule | Risk | Pattern | Mechanism |
|---|---|---|---|
| SEC001 | HIGH | `(a+)+`, `(a*)*` | Nested quantifiers — exponential backtracking O(2^n) |
| SEC002 | HIGH/MEDIUM | `(a\|aa)+` | Overlapping alternation — prefix ambiguity |
| SEC003 | MEDIUM | `(a?)+` | Nullable repetition — zero-width loop |

> **Caveat**: SecureRegex's own DFA-based engine does **not backtrack** and is immune to ReDoS. Findings indicate potential risk in backtracking engines (Python `re`, JavaScript, Java, .NET, PCRE, etc.) only.

---

## Implementation Notes

- **No `re` module** — the Python `re` module is excluded from all core pipeline modules.
- **Pure Python compiler core** — every stage (lexer through minimizer) is implemented from scratch.
- **Structured errors** — every domain error is a `SecureRegexError` subclass. Clients never see raw tracebacks.
- **Safety caps** — `max_dfa_states` prevents subset-construction blowup; `max_computation_steps` guards NFA simulation.

---

## Documentation

| Document | Contents |
|---|---|
| [`docs/architecture.md`](docs/architecture.md) | Full system diagram, component responsibilities, design decisions |
| [`docs/algorithms.md`](docs/algorithms.md) | Thompson's construction, subset construction, Hopcroft — with complexity analysis |
| [`docs/grammar.md`](docs/grammar.md) | Complete EBNF grammar, precedence table, parse error catalogue |
| [`docs/security-analysis.md`](docs/security-analysis.md) | SEC001–SEC003 rules, FIRST set computation, false-positive/negative analysis |
| [`docs/testing.md`](docs/testing.md) | Test inventory, fixture battery, automated vs manual verification checklist |
| [`examples/fixtures.json`](examples/fixtures.json) | 13-pattern battery (7 safe + 6 risky) with expected results |

---

## License

MIT — see [LICENSE](LICENSE)

---

## No Paid Services

This project runs entirely locally. No paid APIs, no cloud services, no telemetry.
