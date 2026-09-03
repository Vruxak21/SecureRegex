# SecureRegex — Architecture

## Pipeline Overview

```
User Input (regex string)
        │
        ▼
┌───────────────┐
│     Lexer     │  Converts raw string → Token stream
│  (backend/    │  Handles: literals, operators, brackets,
│   app/lexer)  │  character classes, quantifiers
└──────┬────────┘
       │ Token[]
       ▼
┌───────────────┐
│    Parser     │  Recursive-descent parser
│  (app/parser) │  Consumes tokens → Abstract Syntax Tree
└──────┬────────┘
       │ ASTNode
       ▼
┌───────────────┐
│   Semantic    │  Validates AST (e.g. valid char ranges,
│   Analyser    │  no unsupported constructs)
│ (app/semantic)│
└──────┬────────┘
       │ Validated ASTNode
       ▼
┌───────────────┐
│  Thompson NFA │  ε-NFA via Thompson's construction
│   (app/nfa)   │  Each AST node maps to a sub-NFA
└──────┬────────┘
       │ NFA
       ▼
┌───────────────┐
│    Subset     │  Powers-et construction: NFA → DFA
│ Construction  │  ε-closure, move, reachable states
│   (app/dfa)   │
└──────┬────────┘
       │ DFA
       ▼
┌───────────────┐
│      DFA      │  Hopcroft's partition-refinement algorithm
│  Minimisation │  Reduces state count to minimum
│ (app/optimizer│
└──────┬────────┘
       │ Minimised DFA
       ▼
┌───────────────┐
│   Security    │  ReDoS heuristics:
│   Analyser    │  - Ambiguous NFA paths
│ (app/security)│  - Nested quantifier detection
└──────┬────────┘
       │ SecurityReport
       ▼
┌───────────────┐
│  FastAPI API  │  REST endpoints — serialise everything
│   (app/api)   │  to JSON for the frontend
└──────┬────────┘
       │ JSON
       ▼
┌───────────────┐
│    Frontend   │  React + TypeScript + Vite
│   (React Flow │  Visualises NFA/DFA graphs, shows report
│    + Tailwind)│
└───────────────┘
```

## Key Design Decisions

### No `re` module
The Python standard library's `re` module is explicitly excluded from all
core pipeline modules. This ensures the implementation is genuinely a
compiler exercise, not a wrapper.

### Pydantic settings
All configuration (limits, CORS, debug flags) lives in `app/config.py`
using `pydantic-settings`. This allows environment-variable overrides
without changing code, which is critical for Docker/CI use.

### Structured errors
Every domain error is a subclass of `SecureRegexError`. A single FastAPI
exception handler maps these to JSON. Callers never see raw Python tracebacks.

### State machine safety caps
`max_nfa_states`, `max_dfa_states`, and `max_computation_steps` prevent
pathological inputs from hanging the server.
