/**
 * Phase 11 — Frontend E2E smoke flow (Vitest + Testing Library).
 *
 * Tests the full in-browser user flow without a live server:
 *   1. App loads → backend polling shows "Backend online"
 *   2. Analyze (a|b)*abb → results dashboard renders with all tabs
 *   3. Security tab shows NONE risk for safe pattern
 *   4. Clear → dashboard disappears
 *   5. Analyze (a+)+ → HIGH risk security warning shown
 *   6. Error path: malformed regex → error banner (no crash, no dashboard)
 *
 * All fetch calls are intercepted via vi.stubGlobal to avoid network deps.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import HomePage from '../src/pages/HomePage'

// ── Shared mock responses ────────────────────────────────────────────────────

const MOCK_HEALTH = { status: 'ok', version: '0.1.0', app: 'SecureRegex' }
const MOCK_INFO = {
  name: 'SecureRegex', version: '0.1.0',
  limits: { max_regex_length: 1000, max_input_length: 10000,
            max_nfa_states: 5000, max_dfa_states: 2000, max_computation_steps: 1000000 },
}

const AUTOMATON_5 = {
  states: [0,1,2,3,4], alphabet: ['a','b'],
  transitions: [
    { from: 0, symbol: 'a', to: 1 }, { from: 0, symbol: 'b', to: 2 },
    { from: 1, symbol: 'a', to: 1 }, { from: 1, symbol: 'b', to: 3 },
    { from: 2, symbol: 'a', to: 1 }, { from: 2, symbol: 'b', to: 2 },
    { from: 3, symbol: 'a', to: 1 }, { from: 3, symbol: 'b', to: 4 },
    { from: 4, symbol: 'a', to: 1 }, { from: 4, symbol: 'b', to: 2 },
  ],
  start: 0, accepting: [4],
}
const AUTOMATON_4 = {
  states: [0,1,2,3], alphabet: ['a','b'],
  transitions: [
    { from: 0, symbol: 'a', to: 1 }, { from: 0, symbol: 'b', to: 0 },
    { from: 1, symbol: 'a', to: 1 }, { from: 1, symbol: 'b', to: 2 },
    { from: 2, symbol: 'a', to: 1 }, { from: 2, symbol: 'b', to: 3 },
    { from: 3, symbol: 'a', to: 1 }, { from: 3, symbol: 'b', to: 0 },
  ],
  start: 0, accepting: [3],
}

const MOCK_ANALYZE_SAFE = {
  success: true,
  tokens: [
    { type: 'LPAREN', value: '(', column: 1 },
    { type: 'CHAR',   value: 'a', column: 2 },
    { type: 'OR',     value: '|', column: 3 },
    { type: 'CHAR',   value: 'b', column: 4 },
    { type: 'RPAREN', value: ')', column: 5 },
    { type: 'STAR',   value: '*', column: 6 },
    { type: 'CHAR',   value: 'a', column: 7 },
    { type: 'CHAR',   value: 'b', column: 8 },
    { type: 'CHAR',   value: 'b', column: 9 },
  ],
  ast: { type: 'Concat', left: { type: 'Star', child: { type: 'Union',
         left: { type: 'Literal', char: 'a' }, right: { type: 'Literal', char: 'b' } } },
         right: { type: 'Literal', char: 'b' } },
  nfa: { states: Array.from({length:14},(_,i)=>i), alphabet: ['a','b'],
         transitions: [{from:0,symbol:'a',to:1}], start: 6, accepting: [13] },
  dfa: AUTOMATON_5,
  minimized_dfa: AUTOMATON_4,
  diagnostics: [],
  security: { overall_risk: 'NONE', findings: [], caveat: 'Findings are heuristic indicators only. DFA-based engine does not backtrack.' },
  stats: {
    regex_length: 9, token_count: 9, ast_node_count: 10,
    nfa_states: 14, nfa_transitions: 16,
    dfa_states: 5, dfa_transitions: 10,
    minimized_dfa_states: 4, dfa_reduction_pct: 20.0,
    overall_security_risk: 'NONE',
  },
}

const MOCK_ANALYZE_RISKY = {
  ...MOCK_ANALYZE_SAFE,
  security: {
    overall_risk: 'HIGH',
    findings: [{
      rule_id: 'SEC001', risk_level: 'HIGH',
      title: 'Nested Quantifiers',
      reason: "A '+' quantifier wraps an expression that itself contains a '+' repetition.",
      explanation: 'May cause catastrophic backtracking in non-DFA engines.',
      recommendation: "Simplify to 'a+'.",
      location: { start: 1, end: 5 },
    }],
    caveat: 'Findings are heuristic indicators only. DFA-based engine does not backtrack.',
  },
  stats: { ...MOCK_ANALYZE_SAFE.stats, overall_security_risk: 'HIGH' },
}

// ── Fetch mock factory ────────────────────────────────────────────────────────

function stubFetch(responses: unknown[]) {
  let call = 0
  vi.stubGlobal('fetch', vi.fn().mockImplementation(async () => {
    const body = responses[Math.min(call++, responses.length - 1)]
    return { ok: true, json: async () => body }
  }))
}

function stubFetchWithError(analyzeError: unknown) {
  let call = 0
  vi.stubGlobal('fetch', vi.fn().mockImplementation(async () => {
    call++
    if (call <= 2) return { ok: true, json: async () => (call === 1 ? MOCK_HEALTH : MOCK_INFO) }
    return { ok: false, json: async () => analyzeError }
  }))
}

function clickAnalyze() {
  fireEvent.click(document.querySelector('#btn-analyze') as HTMLButtonElement)
}

afterEach(() => vi.restoreAllMocks())

// ─────────────────────────────────────────────────────────────────────────────
// 1. App loads and connects
// ─────────────────────────────────────────────────────────────────────────────

describe('E2E smoke: app load', () => {
  beforeEach(() => stubFetch([MOCK_HEALTH, MOCK_INFO]))

  it('renders the main heading', () => {
    render(<HomePage />)
    expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument()
  })

  it('shows connecting initially', () => {
    render(<HomePage />)
    expect(screen.getByText(/connecting/i)).toBeInTheDocument()
  })

  it('shows backend online after health resolves', async () => {
    render(<HomePage />)
    await waitFor(() => expect(screen.getByText(/backend online/i)).toBeInTheDocument())
  })

  it('shows version from health response', async () => {
    render(<HomePage />)
    await waitFor(() => expect(screen.getByText(/backend online/i)).toBeInTheDocument())
    // version string like "v0.1.0" is rendered in nav after health resolves
    expect(screen.getByText(/v0\.1\.0/)).toBeInTheDocument()
  })

  it('regex input is present and focusable', async () => {
    render(<HomePage />)
    await waitFor(() => screen.getByText(/backend online/i))
    expect(screen.getByRole('textbox')).toBeInTheDocument()
  })

  it('Analyze button starts disabled', () => {
    render(<HomePage />)
    const btn = document.querySelector('#btn-analyze') as HTMLButtonElement
    expect(btn).toBeDisabled()
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// 2. Submit (a|b)*abb → full results dashboard
// ─────────────────────────────────────────────────────────────────────────────

describe('E2E smoke: analyze (a|b)*abb', () => {
  beforeEach(() => stubFetch([MOCK_HEALTH, MOCK_INFO, MOCK_ANALYZE_SAFE]))

  it('results dashboard appears after analysis', async () => {
    render(<HomePage />)
    await userEvent.type(screen.getByRole('textbox'), '(a|b)*abb')
    clickAnalyze()
    await waitFor(() => expect(screen.getByTestId('results-dashboard')).toBeInTheDocument())
  })

  it('all 5 top-level tabs are rendered', async () => {
    render(<HomePage />)
    await userEvent.type(screen.getByRole('textbox'), '(a|b)*abb')
    clickAnalyze()
    await waitFor(() => screen.getByTestId('results-dashboard'))
    const tabs = screen.getAllByRole('tab')
    expect(tabs.length).toBe(5)
    expect(screen.getByRole('tab', { name: 'Automata' })).toBeInTheDocument()
  })

  it('Tokens tab shows token type LPAREN', async () => {
    render(<HomePage />)
    await userEvent.type(screen.getByRole('textbox'), '(a|b)*abb')
    clickAnalyze()
    await waitFor(() => screen.getByTestId('results-dashboard'))
    expect(screen.getByText('LPAREN')).toBeInTheDocument()
  })

  it('stats panel shows NFA states = 14', async () => {
    render(<HomePage />)
    await userEvent.type(screen.getByRole('textbox'), '(a|b)*abb')
    clickAnalyze()
    await waitFor(() => screen.getByTestId('results-dashboard'))
    expect(screen.getByText('14')).toBeInTheDocument()
  })

  it('stats panel shows 20.0% DFA reduction', async () => {
    render(<HomePage />)
    await userEvent.type(screen.getByRole('textbox'), '(a|b)*abb')
    clickAnalyze()
    await waitFor(() => screen.getByTestId('results-dashboard'))
    expect(screen.getByText('20.0%')).toBeInTheDocument()
  })

  it('security tab shows NONE risk for (a|b)*abb', async () => {
    render(<HomePage />)
    await userEvent.type(screen.getByRole('textbox'), '(a|b)*abb')
    clickAnalyze()
    await waitFor(() => screen.getByTestId('results-dashboard'))
    await userEvent.click(screen.getByRole('tab', { name: /Security/i }))
    expect(screen.getAllByText(/NONE/i).length).toBeGreaterThanOrEqual(1)
  })

  it('security tab shows the caveat text', async () => {
    render(<HomePage />)
    await userEvent.type(screen.getByRole('textbox'), '(a|b)*abb')
    clickAnalyze()
    await waitFor(() => screen.getByTestId('results-dashboard'))
    await userEvent.click(screen.getByRole('tab', { name: /Security/i }))
    expect(screen.getByText(/heuristic/i)).toBeInTheDocument()
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// 3. Clear resets the UI
// ─────────────────────────────────────────────────────────────────────────────

describe('E2E smoke: Clear button', () => {
  beforeEach(() => stubFetch([MOCK_HEALTH, MOCK_INFO, MOCK_ANALYZE_SAFE]))

  it('Clear hides the results dashboard', async () => {
    render(<HomePage />)
    await userEvent.type(screen.getByRole('textbox'), '(a|b)*abb')
    clickAnalyze()
    await waitFor(() => screen.getByTestId('results-dashboard'))
    await userEvent.click(screen.getByRole('button', { name: /Clear/i }))
    expect(screen.queryByTestId('results-dashboard')).not.toBeInTheDocument()
  })

  it('Clear empties the input', async () => {
    render(<HomePage />)
    await userEvent.type(screen.getByRole('textbox'), '(a|b)*abb')
    clickAnalyze()
    await waitFor(() => screen.getByTestId('results-dashboard'))
    await userEvent.click(screen.getByRole('button', { name: /Clear/i }))
    expect((screen.getByRole('textbox') as HTMLInputElement).value).toBe('')
  })

  it('pipeline steps reappear after Clear', async () => {
    render(<HomePage />)
    await userEvent.type(screen.getByRole('textbox'), '(a|b)*abb')
    clickAnalyze()
    await waitFor(() => screen.getByTestId('results-dashboard'))
    await userEvent.click(screen.getByRole('button', { name: /Clear/i }))
    expect(screen.getByText('Lexer')).toBeInTheDocument()
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// 4. Analyze (a+)+ → HIGH risk security tab
// ─────────────────────────────────────────────────────────────────────────────

describe('E2E smoke: (a+)+ → HIGH risk', () => {
  beforeEach(() => stubFetch([MOCK_HEALTH, MOCK_INFO, MOCK_ANALYZE_RISKY]))

  it('dashboard appears for (a+)+', async () => {
    render(<HomePage />)
    await userEvent.type(screen.getByRole('textbox'), '(a+)+')
    clickAnalyze()
    await waitFor(() => expect(screen.getByTestId('results-dashboard')).toBeInTheDocument())
  })

  it('Security tab shows HIGH risk badge', async () => {
    render(<HomePage />)
    await userEvent.type(screen.getByRole('textbox'), '(a+)+')
    clickAnalyze()
    await waitFor(() => screen.getByTestId('results-dashboard'))
    await userEvent.click(screen.getByRole('tab', { name: /Security/i }))
    expect(screen.getByText(/Overall Risk: HIGH/i)).toBeInTheDocument()
  })

  it('Security tab shows SEC001 rule', async () => {
    render(<HomePage />)
    await userEvent.type(screen.getByRole('textbox'), '(a+)+')
    clickAnalyze()
    await waitFor(() => screen.getByTestId('results-dashboard'))
    await userEvent.click(screen.getByRole('tab', { name: /Security/i }))
    expect(screen.getByText('SEC001')).toBeInTheDocument()
  })

  it('Nested Quantifiers title is shown', async () => {
    render(<HomePage />)
    await userEvent.type(screen.getByRole('textbox'), '(a+)+')
    clickAnalyze()
    await waitFor(() => screen.getByTestId('results-dashboard'))
    await userEvent.click(screen.getByRole('tab', { name: /Security/i }))
    expect(screen.getByText('Nested Quantifiers')).toBeInTheDocument()
  })

  it('risk badge in header shows HIGH', async () => {
    render(<HomePage />)
    await userEvent.type(screen.getByRole('textbox'), '(a+)+')
    clickAnalyze()
    await waitFor(() => screen.getByTestId('results-dashboard'))
    // The header risk badge
    expect(screen.getByText(/HIGH risk/i)).toBeInTheDocument()
  })

  it('caveat is shown even for HIGH risk', async () => {
    render(<HomePage />)
    await userEvent.type(screen.getByRole('textbox'), '(a+)+')
    clickAnalyze()
    await waitFor(() => screen.getByTestId('results-dashboard'))
    await userEvent.click(screen.getByRole('tab', { name: /Security/i }))
    expect(screen.getByText(/heuristic/i)).toBeInTheDocument()
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// 5. Malformed regex → error banner, no crash
// ─────────────────────────────────────────────────────────────────────────────

describe('E2E smoke: malformed regex error path', () => {
  beforeEach(() => stubFetchWithError({
    error: 'PARSE_ERROR',
    message: "Missing closing ')' at position 1",
    position: { line: 1, column: 1 },
  }))

  it('error banner appears with structured message', async () => {
    render(<HomePage />)
    await userEvent.type(screen.getByRole('textbox'), '(')
    clickAnalyze()
    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument())
    expect(screen.getByRole('alert').textContent).toContain("Missing closing ')'")
  })

  it('dashboard does NOT appear on error', async () => {
    render(<HomePage />)
    await userEvent.type(screen.getByRole('textbox'), '(')
    clickAnalyze()
    await waitFor(() => screen.getByRole('alert'))
    expect(screen.queryByTestId('results-dashboard')).not.toBeInTheDocument()
  })

  it('error banner shows column number', async () => {
    render(<HomePage />)
    await userEvent.type(screen.getByRole('textbox'), '(')
    clickAnalyze()
    await waitFor(() => screen.getByRole('alert'))
    expect(screen.getByRole('alert').textContent).toMatch(/column 1/i)
  })

  it('page does not crash — no thrown exception', () => {
    expect(() => render(<HomePage />)).not.toThrow()
  })

  it('Analyze button re-enables after error (not stuck loading)', async () => {
    render(<HomePage />)
    const input = screen.getByRole('textbox')
    await userEvent.type(input, '(')
    clickAnalyze()
    await waitFor(() => screen.getByRole('alert'))
    const btn = document.querySelector('#btn-analyze') as HTMLButtonElement
    expect(btn).not.toBeDisabled()
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// 6. Example patterns are clickable shortcuts
// ─────────────────────────────────────────────────────────────────────────────

describe('E2E smoke: example pattern shortcuts', () => {
  beforeEach(() => stubFetch([MOCK_HEALTH, MOCK_INFO]))

  it('(a|b)*abb example button loads pattern into input', async () => {
    render(<HomePage />)
    await userEvent.click(screen.getByText('(a|b)*abb'))
    expect((screen.getByRole('textbox') as HTMLInputElement).value).toBe('(a|b)*abb')
  })

  it('(a+)+ example button loads pattern into input', async () => {
    render(<HomePage />)
    await userEvent.click(screen.getByText('(a+)+'))
    expect((screen.getByRole('textbox') as HTMLInputElement).value).toBe('(a+)+')
  })

  it('(a|aa)+ example button is present', () => {
    render(<HomePage />)
    expect(screen.getByText('(a|aa)+')).toBeInTheDocument()
  })

  it('loading an example enables the Analyze button', async () => {
    render(<HomePage />)
    await userEvent.click(screen.getByText('(a|b)*abb'))
    const btn = document.querySelector('#btn-analyze') as HTMLButtonElement
    expect(btn).not.toBeDisabled()
  })
})
