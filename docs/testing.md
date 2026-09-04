# SecureRegex — Testing Documentation

> **Status**: Phase 11 complete.
> Backend: **1097** pytest tests · Frontend: **123** Vitest tests · **0 failures**.

---

## Table of Contents

1. [Test Infrastructure](#1-test-infrastructure)
2. [Backend Test Suite](#2-backend-test-suite)
3. [Frontend Test Suite](#3-frontend-test-suite)
4. [Regex Battery Fixtures](#4-regex-battery-fixtures)
5. [What Is Covered Automatically](#5-what-is-covered-automatically)
6. [What Requires Manual Verification](#6-what-requires-manual-verification)
7. [Running the Tests](#7-running-the-tests)

---

## 1. Test Infrastructure

| Layer | Framework | Runner | Location |
|---|---|---|---|
| Backend unit | **pytest 9.x** | `pytest` in venv | `backend/tests/` |
| Backend E2E | **pytest + FastAPI TestClient** | Same | `backend/tests/test_e2e.py` |
| Frontend unit | **Vitest + @testing-library/react** | `npm test` | `frontend/tests/` |
| Frontend E2E smoke | **Vitest + @testing-library/react** | Same | `frontend/tests/Phase11.test.tsx` |

No external service is required for any automated test — the FastAPI `TestClient` spins up the full ASGI app in-process, and all frontend fetch calls are mocked via `vi.stubGlobal('fetch', ...)`.

---

## 2. Backend Test Suite

### File inventory

| File | Phase | Description | Tests |
|---|---|---|---|
| `test_phase0.py` | 0 | Project scaffolding, imports, settings | 21 |
| `test_lexer.py` | 1 | Token types, special chars, char classes | 80 |
| `test_parser.py` | 2 | AST construction, precedence, ParseError | 124 |
| `test_ast.py` | 2 | AST serialisation to JSON-friendly dict | 48 |
| `test_semantic.py` | 3 | SEM001/SEM002 diagnostics, empty expr | 63 |
| `test_nfa.py` | 4 | Thompson's construction, ε-closure, state counts | 97 |
| `test_dfa.py` | 5 | Subset construction, determinism, cross-check | 112 |
| `test_minimization.py` | 6 | Hopcroft's algorithm, reduction stats | 84 |
| `test_security.py` | 7 | SEC001/SEC002/SEC003 rules, caveat text | 79 |
| `test_api.py` | 8 | `/api/v1/analyze` + `/api/v1/test` integration | 124 |
| **`test_e2e.py`** | **11** | **Full battery + robustness + guards** | **299** |
| **Total** | | | **1097** |

### E2E test groups (`test_e2e.py`)

| Class | What it checks |
|---|---|
| `TestBatteryAnalyze` | All 13 fixture patterns: HTTP 200, success flag, non-empty tokens, minimized≤DFA states, reduction in [0,100], security risk valid, AST type key, caveat present, no traceback |
| `TestBatterySecurityRisk` | Safe patterns → NONE; risky patterns → expected risk level; rule_ids match; finding fields complete |
| `TestBatteryAcceptReject` | accept/reject strings from fixtures pass through `/api/test`; path starts at start state |
| `TestErrorPaths` | Every error path returns 4xx with structured JSON; no raw tracebacks; `@` is a valid literal; `[z-a]` returns SEM001 diagnostic at 200; empty regex → 4xx |
| `TestGuards` | `max_regex_length+1` → 422 REGEX_TOO_LONG; at-limit succeeds; `max_input_length+1` → 422 INPUT_TOO_LONG; DFA blowup guard; missing fields → 422; wrong content-type → 415/422 |
| `TestStatisticsConsistency` | All cross-field invariants: minimized≤dfa for all patterns; `stats.overall_security_risk` matches `security.overall_risk`; token count, regex length exact |
| `TestHighRiskEndToEnd` | `(a+)+`, `(a*)*`, `(a*)+`, `(a|aa)+` → all HIGH with correct rule IDs; SEC003 for `(a?)+`; caveat mentions DFA/backtrack |
| `TestResponseShape` | Every top-level key present; `nfa/dfa/minimized_dfa` all have `states/alphabet/transitions/start/accepting`; all stats keys present |

---

## 3. Frontend Test Suite

### File inventory

| File | Phase | Description | Tests |
|---|---|---|---|
| `HomePage.test.tsx` | 0 | Phase 0 landing page structure | 9 |
| `Phase9.test.tsx` | 9 | Input, examples, error banner, 7-tab dashboard | 35 |
| `Phase10.test.tsx` | 10 | `automataToFlow` pure utility, AutomataGraph, AutomataStateNode, traversal highlighting | 48 |
| **`Phase11.test.tsx`** | **11** | **E2E smoke: load → safe → clear → risky → error** | **31** |
| **Total** | | | **123** |

### E2E smoke groups (`Phase11.test.tsx`)

| Group | What it checks |
|---|---|
| App load | Heading, connecting→online transition, version in nav, Analyze disabled |
| `(a|b)*abb` analysis | Dashboard, 7 tabs, LPAREN token, 14 NFA states, 20% reduction, NONE risk, caveat |
| Clear | Dashboard hidden, input empty, pipeline steps visible again |
| `(a+)+` HIGH risk | Dashboard, Security tab shows HIGH badge + SEC001 + "Nested Quantifiers" + caveat |
| Malformed regex | Error banner with message + column, no dashboard, button re-enables |
| Example shortcuts | Clicking `(a|b)*abb`/`(a+)+` fills input; Analyze button enables |

### Mocking strategy

React Flow (`@xyflow/react`) is mocked because jsdom has no `ResizeObserver` or SVG layout. The mock renders one `<div data-testid="node-{id}">` per node with `data-accepting`, `data-start`, `data-highlighted` attributes — so graph node counts and flags are still fully tested without a real browser.

All `fetch` calls are intercepted via `vi.stubGlobal('fetch', ...)` per test group.

---

## 4. Regex Battery Fixtures

Source: [`examples/fixtures.json`](../examples/fixtures.json)

### Safe patterns (expect `overall_risk: NONE`)

| ID | Pattern | Description | Accepts | Rejects |
|---|---|---|---|---|
| safe_01 | `(a\|b)*abb` | Classic Dragon Book DFA | abb, aabb, babb | "", ab, abba |
| safe_02 | `[a-z]+` | Char class repetition | a, hello | "", A, 1 |
| safe_03 | `ab\|cb` | Simple alternation, 5→3 min | ab, cb | "", a, abc |
| safe_04 | `[0-9]*` | Zero or more digits | "", 0, 123 | a, 12a |
| safe_05 | `a?b` | Optional a + mandatory b | b, ab | "", a, aab |
| safe_06 | `(a\|b)+` | Disjoint alternation + plus | a, b, ab | "", c |
| safe_07 | `a*b*` | Sequential star | "", a, b, ab | ba, aba |

### Risky patterns (expect `overall_risk: HIGH` or `MEDIUM`)

| ID | Pattern | Expected risk | Rule | Description |
|---|---|---|---|---|
| risky_01 | `(a+)+` | HIGH | SEC001 | Nested quantifiers |
| risky_02 | `(a*)*` | HIGH | SEC001 | Nested star |
| risky_03 | `(a\|aa)+` | HIGH | SEC002 | Overlapping alternation |
| risky_04 | `(a?)+` | MEDIUM | SEC003 | Nullable repetition |
| risky_05 | `([a-z]+)+` | HIGH | SEC001 | Char class under nested quantifier |
| risky_06 | `(a*)+` | HIGH | SEC001 | Star under plus |

> **Note**: Risk findings are *heuristic indicators only*. SecureRegex's own DFA-based engine does not backtrack and is immune to ReDoS. Findings indicate potential risk in backtracking engines (Python `re`, JavaScript, Java, .NET, PCRE, etc.).

---

## 5. What Is Covered Automatically

| Category | Automated? | Details |
|---|---|---|
| Lexer token types | ✅ | All 18 token types, position tracking |
| Parser precedence (`*`/`+`/`?` > concat > `\|`) | ✅ | 40+ precedence and associativity tests |
| AST serialization | ✅ | All 8 node types → JSON round-trip |
| Semantic SEM001 / SEM002 / SEM003 | ✅ | Invalid ranges, empty branches |
| Thompson NFA state/transition counts | ✅ | All 8 rule types; ε-transitions verified |
| DFA determinism | ✅ | ≤1 transition per (state, symbol) |
| NFA ↔ DFA language equivalence | ✅ | Cross-check on 20+ strings |
| Hopcroft minimization correctness | ✅ | Language equivalence + state count |
| SEC001/SEC002/SEC003 security rules | ✅ | 30+ risky patterns; caveat in all findings |
| API response shape | ✅ | All top-level + nested keys |
| HTTP status codes (200/4xx/422) | ✅ | All error paths |
| No raw traceback in any response | ✅ | Checked across all battery patterns |
| Max-regex-length guard (API) | ✅ | 1001-char regex → 422 REGEX_TOO_LONG |
| Max-input-length guard (API) | ✅ | 10001-char input → 422 INPUT_TOO_LONG |
| Statistics invariants | ✅ | minimized≤dfa, reduction in [0,100] |
| Accept/reject correctness | ✅ | 50+ strings across 13 fixtures |
| Frontend: component rendering | ✅ | All 7 dashboard tabs, security tab |
| Frontend: error banner | ✅ | Message + column, no crash |
| Frontend: graph node/edge counts | ✅ | Via mocked React Flow |
| Frontend: traversal highlighting | ✅ | isHighlighted per step |
| Frontend: E2E smoke flows | ✅ | safe pattern → clear → risky pattern |

---

## 6. What Requires Manual Verification

The following cannot be verified by automated tests and should be checked during the demo:

| Category | Why Manual? | How to Verify |
|---|---|---|
| **React Flow zoom/pan** | Requires real browser with DOM layout/events | Open app, drag and scroll the graph canvas |
| **React Flow node positioning** | Layout algorithm uses floats; pixel equality is brittle | Visually confirm circular layout looks sensible |
| **Click-to-inspect node panel** | Pointer events in jsdom are limited | Click a state in the browser; inspector panel should appear |
| **Step-through traversal animation feel** | Timing/visual impression | Submit `(a|b)*abb`, switch to Test Regex tab, step through "abb" with ◀▶ |
| **Scrollbar / overflow behaviour** | CSS rendering | Verify large NFA transition tables scroll properly |
| **Docker compose full stack** | Requires Docker | `docker-compose up` and navigate to `localhost:5173` |
| **CORS headers in production** | Network-level; not tested by TestClient | Set `SECUREREGEX_CORS_ORIGINS` and test from a different port |
| **Long regex performance** | Real wall-clock time | Submit a 500-char regex; verify response is fast |
| **Browser compatibility** | Different JS engines | Test in Chrome, Firefox, Safari |
| **Font loading (Google Fonts)** | Network dependency | Verify Inter/JetBrains Mono render correctly online |
| **Responsiveness / mobile layout** | CSS media queries | Resize to 375px; verify layout doesn't break |
| **API Docs page (`/docs`)** | FastAPI Swagger UI | Navigate to `localhost:8000/docs` and try the endpoints manually |

---

## 7. Running the Tests

### Backend

```bash
cd backend
source .venv/bin/activate

# All tests
pytest -q

# E2E only
pytest tests/test_e2e.py -v

# Specific phase
pytest tests/test_security.py -v
```

### Frontend

```bash
cd frontend

# All tests
npm test

# Watch mode during development
npm run test:watch   # if configured; otherwise: npx vitest

# Specific file
npx vitest tests/Phase11.test.tsx
```

### Expected output (Phase 11 baseline)

```
Backend:  1097 passed  in  ~0.7s
Frontend:  123 passed  in  ~2.5s
```
