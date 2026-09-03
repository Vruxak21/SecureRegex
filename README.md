# SecureRegex

> **Compiler-based Regular Expression Security Analyzer and Automata Optimizer**  
> Academic + Portfolio project — hand-written Lexer → Parser → NFA → DFA → Security Analyzer pipeline.

[![Python](https://img.shields.io/badge/Python-3.12+-blue?logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green?logo=fastapi)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18+-61DAFB?logo=react)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.5+-3178C6?logo=typescript)](https://typescriptlang.org)
[![Vite](https://img.shields.io/badge/Vite-5+-646CFF?logo=vite)](https://vitejs.dev)

---

## What is SecureRegex?

SecureRegex analyses regular expressions for **security vulnerabilities** (primarily ReDoS) and **structural correctness** using a fully hand-written compiler pipeline. It does **not** use Python's `re` module, or any third-party regex parser, for its core engine — every stage (lexing, parsing, NFA/DFA construction, minimisation) is implemented from scratch.

---

## Architecture

```
Regex string
  → Lexer           (tokenises the pattern)
  → Parser          (recursive-descent → AST)
  → Semantic Analyser (validates AST)
  → Thompson NFA    (ε-NFA from AST)
  → Subset Construction (NFA → DFA)
  → DFA Minimisation (Hopcroft's algorithm)
  → Security Analyser (ReDoS heuristics)
  → JSON report     (consumed by frontend)
```

---

## Project Structure

```
secureregex/
├── backend/
│   ├── app/
│   │   ├── lexer/          # Tokeniser (Phase 1)
│   │   ├── parser/         # Recursive-descent parser (Phase 2)
│   │   ├── ast/            # AST node definitions (Phase 2)
│   │   ├── semantic/       # Semantic analysis (Phase 3)
│   │   ├── nfa/            # Thompson NFA construction (Phase 4)
│   │   ├── dfa/            # Subset construction + minimisation (Phase 5)
│   │   ├── optimizer/      # DFA optimiser hooks (Phase 5)
│   │   ├── security/       # ReDoS analyser (Phase 6)
│   │   ├── api/            # FastAPI routers
│   │   ├── config.py       # Pydantic settings
│   │   ├── exceptions.py   # Structured exception hierarchy
│   │   └── main.py         # App entry-point
│   ├── tests/              # pytest test suite
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── api/            # Typed fetch client
│   │   ├── components/     # Shared UI components
│   │   ├── pages/          # Route-level pages
│   │   ├── visualizations/ # React Flow automata graphs
│   │   └── types/          # Shared TypeScript types
│   ├── tests/              # Vitest test suite
│   ├── vite.config.ts
│   └── Dockerfile
├── docs/                   # Architecture & algorithm docs
├── examples/               # Sample regex patterns
├── docker-compose.yml
└── README.md
```

---

## Quick Start

### Option A — Docker (recommended, no local Python/Node needed)

> Requires: [Docker Desktop](https://www.docker.com/products/docker-desktop/) (free)

```bash
git clone <repo-url>
cd secureregex
docker-compose up --build
```

- Frontend: http://localhost:5173  
- Backend API docs: http://localhost:8000/docs  
- Health check: http://localhost:8000/health

### Option B — Local development (no Docker)

#### Backend

> Requires: Python 3.12 (3.14 users: add `--only-binary=:all:` flag to pip)

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# Python 3.12 / 3.13:
pip install -r requirements.txt -r requirements-dev.txt

# Python 3.14 (macOS arm64 — binary wheels only):
pip install --only-binary=:all: -r requirements.txt -r requirements-dev.txt

# Start server
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

### Backend (pytest)

```bash
cd backend
source .venv/bin/activate
pytest                    # runs all tests with -v --tb=short
```

### Frontend (Vitest)

```bash
cd frontend
npm test                  # vitest run (single pass)
npm run test:watch        # watch mode
```

---

## Configuration

All backend settings are controlled by environment variables prefixed with `SECUREREGEX_`:

| Variable | Default | Description |
|---|---|---|
| `SECUREREGEX_DEBUG` | `false` | Enable debug logging |
| `SECUREREGEX_MAX_REGEX_LENGTH` | `1000` | Max regex pattern length |
| `SECUREREGEX_MAX_INPUT_LENGTH` | `10000` | Max test-string length |
| `SECUREREGEX_MAX_NFA_STATES` | `5000` | Safety cap on NFA states |
| `SECUREREGEX_MAX_DFA_STATES` | `2000` | Safety cap on DFA states |
| `SECUREREGEX_MAX_COMPUTATION_STEPS` | `1000000` | Simulation step limit |
| `SECUREREGEX_CORS_ORIGINS` | `["http://localhost:5173"]` | Allowed CORS origins |

---

## Development Phases

| Phase | Status | Scope |
|---|---|---|
| **Phase 0** | ✅ Done | Project setup, FastAPI skeleton, Vite frontend, Docker, tests |
| **Phase 1** | 🔜 Next | Lexer — tokenise regex patterns |
| **Phase 2** | 🔜 | Parser — recursive-descent → AST |
| **Phase 3** | 🔜 | Semantic Analyser |
| **Phase 4** | 🔜 | Thompson NFA construction |
| **Phase 5** | 🔜 | Subset construction + DFA minimisation |
| **Phase 6** | 🔜 | ReDoS security analyser |
| **Phase 7** | 🔜 | Full REST API + Frontend UI |

---

## License

MIT — see [LICENSE](LICENSE)

---

## No Paid Services

This project runs entirely locally. No paid APIs, no cloud services, no telemetry.
