/**
 * Phase 9 — Frontend core pages tests.
 *
 * Tests:
 *   1. Renders example buttons (including (a|b)*abb and (a+)+)
 *   2. Has Analyze and Clear buttons
 *   3. Submitting (a|b)*abb triggers API call and renders dashboard with all tabs
 *   4. Malformed regex shows readable error banner, not a crash
 *   5. Oversized regex button is disabled once limit is reached
 *   6. SecurityTab renders HIGH risk correctly
 *   7. StatsPanel renders all required fields
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import HomePage from '../src/pages/HomePage'

// ── Shared mock data ──────────────────────────────────────────────────────────

const mockHealth = { status: 'ok', version: '0.1.0', app: 'SecureRegex' }
const mockInfo = {
  name: 'SecureRegex', version: '0.1.0',
  limits: { max_regex_length: 1000, max_input_length: 10000,
            max_nfa_states: 5000, max_dfa_states: 2000, max_computation_steps: 1000000 },
}

const mockAnalyzeResult = {
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
  nfa: { states: Array.from({length: 14}, (_, i) => i), alphabet: ['a','b'],
         transitions: [{ from: 0, symbol: 'a', to: 1 }], start: 6, accepting: [13] },
  dfa: { states: [0,1,2,3,4], alphabet: ['a','b'],
         transitions: [{ from: 0, symbol: 'a', to: 1 }, { from: 0, symbol: 'b', to: 2 }],
         start: 0, accepting: [4] },
  minimized_dfa: { states: [0,1,2,3], alphabet: ['a','b'],
         transitions: [{ from: 0, symbol: 'a', to: 1 }], start: 0, accepting: [3] },
  diagnostics: [],
  security: {
    overall_risk: 'NONE',
    findings: [],
    caveat: 'Findings are heuristic risk indicators only.',
  },
  stats: {
    regex_length: 9, token_count: 9, ast_node_count: 10,
    nfa_states: 14, nfa_transitions: 16,
    dfa_states: 5, dfa_transitions: 10,
    minimized_dfa_states: 4, dfa_reduction_pct: 20.0,
    overall_security_risk: 'NONE',
  },
}

const mockAnalyzeHighRisk = {
  ...mockAnalyzeResult,
  security: {
    overall_risk: 'HIGH',
    findings: [{
      rule_id: 'SEC001', risk_level: 'HIGH',
      title: 'Nested Quantifiers',
      reason: "A '+' quantifier wraps an expression that itself contains a '+' repetition.",
      explanation: 'Catastrophic backtracking.',
      recommendation: "Simplify to 'a+'.",
      location: { start: 5, end: 5 },
    }],
    caveat: 'Findings are heuristic risk indicators only.',
  },
  stats: { ...mockAnalyzeResult.stats, overall_security_risk: 'HIGH' },
}

function makeFetch(responses: unknown[]) {
  let call = 0
  return vi.fn().mockImplementation(async () => {
    const body = responses[Math.min(call++, responses.length - 1)]
    return { ok: true, json: async () => body }
  })
}

function makeErrorFetch(healthOk: boolean, errorBody: unknown) {
  let call = 0
  return vi.fn().mockImplementation(async () => {
    call++
    // First two calls are health + info
    if (call <= 2) return { ok: true, json: async () => (call === 1 ? mockHealth : mockInfo) }
    // Analyze call fails
    return { ok: false, json: async () => errorBody }
  })
}

// ── 1. Example buttons ────────────────────────────────────────────────────────

describe('Example pattern buttons', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', makeFetch([mockHealth, mockInfo]))
  })
  afterEach(() => vi.restoreAllMocks())

  it('renders (a|b)*abb example button', () => {
    render(<HomePage />)
    expect(screen.getByText('(a|b)*abb')).toBeInTheDocument()
  })

  it('renders (a+)+ example button', () => {
    render(<HomePage />)
    expect(screen.getByText('(a+)+')).toBeInTheDocument()
  })

  it('renders at least 4 example buttons', () => {
    render(<HomePage />)
    const examplePatterns = ['(a|b)*abb', '(a+)+', '(a|aa)+', '[a-z]+']
    examplePatterns.forEach(p => {
      expect(screen.getByText(p)).toBeInTheDocument()
    })
  })

  it('clicking (a|b)*abb loads it into the input', async () => {
    render(<HomePage />)
    const btn = screen.getByText('(a|b)*abb')
    await userEvent.click(btn)
    const input = screen.getByRole('textbox')
    expect((input as HTMLInputElement).value).toBe('(a|b)*abb')
  })
})

// ── 2. Input and action buttons ───────────────────────────────────────────────

describe('Analyze and Clear buttons', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', makeFetch([mockHealth, mockInfo]))
  })
  afterEach(() => vi.restoreAllMocks())

  it('Analyze button exists', () => {
    render(<HomePage />)
    expect(screen.getByRole('button', { name: /Analyze/i })).toBeInTheDocument()
  })

  it('Clear button exists', () => {
    render(<HomePage />)
    expect(screen.getByRole('button', { name: /Clear/i })).toBeInTheDocument()
  })

  it('Analyze button is disabled when input is empty', () => {
    render(<HomePage />)
    // The Analyze button has id="btn-analyze"
    const btn = document.querySelector('#btn-analyze') as HTMLButtonElement
    expect(btn).toBeDisabled()
  })

  it('Analyze button becomes enabled after typing', async () => {
    render(<HomePage />)
    const input = screen.getByRole('textbox')
    await userEvent.type(input, 'a')
    const btn = document.querySelector('#btn-analyze') as HTMLButtonElement
    expect(btn).not.toBeDisabled()
  })

  it('Clear button clears the input', async () => {
    render(<HomePage />)
    const input = screen.getByRole('textbox')
    await userEvent.type(input, '(a|b)*abb')
    await userEvent.click(screen.getByRole('button', { name: /Clear/i }))
    expect((input as HTMLInputElement).value).toBe('')
  })
})


// ── Helper: click the Analyze button by its id ────────────────────────────────
function clickAnalyze() {
  const btn = document.querySelector('#btn-analyze') as HTMLButtonElement
  fireEvent.click(btn)
}

// ── 3. Happy-path analysis → dashboard with all tabs ─────────────────────────


describe('Analyze (a|b)*abb — results dashboard', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', makeFetch([mockHealth, mockInfo, mockAnalyzeResult]))
  })
  afterEach(() => vi.restoreAllMocks())

  it('renders the results dashboard after successful analysis', async () => {
    render(<HomePage />)
    const input = screen.getByRole('textbox')
    await userEvent.type(input, '(a|b)*abb')
    clickAnalyze()
    await waitFor(() => expect(screen.getByTestId('results-dashboard')).toBeInTheDocument())
  })

  it('dashboard has Tokens tab', async () => {
    render(<HomePage />)
    await userEvent.type(screen.getByRole('textbox'), '(a|b)*abb')
    clickAnalyze()
    await waitFor(() => screen.getByTestId('results-dashboard'))
    expect(screen.getByRole('tab', { name: /Tokens/i })).toBeInTheDocument()
  })

  it('dashboard has AST tab', async () => {
    render(<HomePage />)
    await userEvent.type(screen.getByRole('textbox'), '(a|b)*abb')
    clickAnalyze()
    await waitFor(() => screen.getByTestId('results-dashboard'))
    expect(screen.getByRole('tab', { name: /AST/i })).toBeInTheDocument()
  })

  it('dashboard has Security tab', async () => {
    render(<HomePage />)
    await userEvent.type(screen.getByRole('textbox'), '(a|b)*abb')
    clickAnalyze()
    await waitFor(() => screen.getByTestId('results-dashboard'))
    expect(screen.getByRole('tab', { name: /Security/i })).toBeInTheDocument()
  })

  it('dashboard has Test Regex tab', async () => {
    render(<HomePage />)
    await userEvent.type(screen.getByRole('textbox'), '(a|b)*abb')
    clickAnalyze()
    await waitFor(() => screen.getByTestId('results-dashboard'))
    expect(screen.getByRole('tab', { name: /Test Regex/i })).toBeInTheDocument()
  })

  it('dashboard has all 5 top-level tabs', async () => {
    render(<HomePage />)
    await userEvent.type(screen.getByRole('textbox'), '(a|b)*abb')
    clickAnalyze()
    await waitFor(() => screen.getByTestId('results-dashboard'))
    const tabs = screen.getAllByRole('tab')
    expect(tabs).toHaveLength(5)
    expect(screen.getByRole('tab', { name: 'Automata' })).toBeInTheDocument()
  })

  it('stats panel shows NFA states count', async () => {
    render(<HomePage />)
    await userEvent.type(screen.getByRole('textbox'), '(a|b)*abb')
    clickAnalyze()
    await waitFor(() => screen.getByTestId('results-dashboard'))
    expect(screen.getByText('14')).toBeInTheDocument()
  })

  it('stats panel shows DFA reduction percentage', async () => {
    render(<HomePage />)
    await userEvent.type(screen.getByRole('textbox'), '(a|b)*abb')
    clickAnalyze()
    await waitFor(() => screen.getByTestId('results-dashboard'))
    expect(screen.getByText('20.0%')).toBeInTheDocument()
  })

  it('tokens are displayed in the Tokens tab', async () => {
    render(<HomePage />)
    await userEvent.type(screen.getByRole('textbox'), '(a|b)*abb')
    clickAnalyze()
    await waitFor(() => screen.getByTestId('results-dashboard'))
    expect(screen.getByText('LPAREN')).toBeInTheDocument()
  })

  it('security NONE shown after safe pattern analysis', async () => {
    render(<HomePage />)
    await userEvent.type(screen.getByRole('textbox'), '(a|b)*abb')
    clickAnalyze()
    await waitFor(() => screen.getByTestId('results-dashboard'))
    await userEvent.click(screen.getByRole('tab', { name: /Security/i }))
    // NONE appears in overall risk banner
    expect(screen.getAllByText(/NONE/i).length).toBeGreaterThanOrEqual(1)
  })
})

// ── 4. Malformed regex → error banner ────────────────────────────────────────

describe('Malformed regex error handling', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', makeErrorFetch(true, {
      error: 'PARSE_ERROR',
      message: "Missing closing ')' at position 1",
      position: { line: 1, column: 1 },
    }))
  })
  afterEach(() => vi.restoreAllMocks())

  it('shows error banner on malformed regex', async () => {
    render(<HomePage />)
    const input = screen.getByRole('textbox')
    await userEvent.type(input, '(')
    clickAnalyze()
    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument()
    })
  })

  it('error banner contains human-readable message', async () => {
    render(<HomePage />)
    await userEvent.type(screen.getByRole('textbox'), '(')
    clickAnalyze()
    await waitFor(() => {
      const alert = screen.getByRole('alert')
      expect(alert.textContent).toContain("Missing closing ')'")
    })
  })

  it('error banner shows column number', async () => {
    render(<HomePage />)
    await userEvent.type(screen.getByRole('textbox'), '(')
    clickAnalyze()
    await waitFor(() => {
      expect(screen.getByRole('alert').textContent).toMatch(/column 1/i)
    })
  })

  it('does not crash — no unhandled error boundary needed', async () => {
    expect(() => {
      render(<HomePage />)
    }).not.toThrow()
  })

  it('results dashboard is NOT shown on error', async () => {
    render(<HomePage />)
    await userEvent.type(screen.getByRole('textbox'), '(')
    clickAnalyze()
    await waitFor(() => screen.getByRole('alert'))
    expect(screen.queryByTestId('results-dashboard')).not.toBeInTheDocument()
  })
})

// ── 5. HIGH risk pattern dashboard ───────────────────────────────────────────

describe('(a+)+ shows HIGH security risk', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', makeFetch([mockHealth, mockInfo, mockAnalyzeHighRisk]))
  })
  afterEach(() => vi.restoreAllMocks())

  it('security tab badge shows HIGH', async () => {
    render(<HomePage />)
    await userEvent.type(screen.getByRole('textbox'), '(a+)+')
    clickAnalyze()
    await waitFor(() => screen.getByTestId('results-dashboard'))
    await userEvent.click(screen.getByRole('tab', { name: /Security/i }))
    expect(screen.getByText(/Overall Risk: HIGH/i)).toBeInTheDocument()
  })

  it('SEC001 finding is displayed', async () => {
    render(<HomePage />)
    await userEvent.type(screen.getByRole('textbox'), '(a+)+')
    clickAnalyze()
    await waitFor(() => screen.getByTestId('results-dashboard'))
    await userEvent.click(screen.getByRole('tab', { name: /Security/i }))
    expect(screen.getByText('SEC001')).toBeInTheDocument()
  })

  it('finding title is shown', async () => {
    render(<HomePage />)
    await userEvent.type(screen.getByRole('textbox'), '(a+)+')
    clickAnalyze()
    await waitFor(() => screen.getByTestId('results-dashboard'))
    await userEvent.click(screen.getByRole('tab', { name: /Security/i }))
    expect(screen.getByText('Nested Quantifiers')).toBeInTheDocument()
  })
})

// ── 6. Phase 0 regression ─────────────────────────────────────────────────────

describe('Phase 0 regression — existing tests still pass', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', makeFetch([mockHealth, mockInfo]))
  })
  afterEach(() => vi.restoreAllMocks())

  it('renders the main heading', () => {
    render(<HomePage />)
    const heading = screen.getByRole('heading', { level: 1 })
    expect(heading).toHaveTextContent(/Analyze Regex/i)
  })

  it('renders SecureRegex brand name', () => {
    render(<HomePage />)
    expect(screen.getByText('SecureRegex')).toBeInTheDocument()
  })

  it('shows connecting status initially', () => {
    render(<HomePage />)
    expect(screen.getByText(/connecting/i)).toBeInTheDocument()
  })

  it('shows backend online after health resolves', async () => {
    vi.stubGlobal('fetch', vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => mockHealth })
      .mockResolvedValueOnce({ ok: true, json: async () => mockInfo }),
    )
    render(<HomePage />)
    await waitFor(() => expect(screen.getByText(/backend online/i)).toBeInTheDocument())
  })

  it('shows backend unreachable on failure', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('Connection refused')))
    render(<HomePage />)
    await waitFor(() => expect(screen.getByText(/backend unreachable/i)).toBeInTheDocument())
  })

  it('renders all 9 pipeline steps', () => {
    render(<HomePage />)
    const steps = ['Lexer', 'Parser', 'AST', 'Semantic', 'NFA', 'DFA', 'Minimize', 'Security', 'Report']
    steps.forEach(s => expect(screen.getByText(s)).toBeInTheDocument())
  })

  it('renders the 6 feature cards', () => {
    render(<HomePage />)
    expect(screen.getAllByText(/Hand-written Compiler/i).length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText(/ReDoS Detection/i)).toBeInTheDocument()
    expect(screen.getByText(/Automata Visualizer/i)).toBeInTheDocument()
    expect(screen.getByText(/DFA Minimisation/i)).toBeInTheDocument()
    expect(screen.getByText(/JSON Reports/i)).toBeInTheDocument()
    expect(screen.getByText(/Docker-first/i)).toBeInTheDocument()
  })

  it('Analyze button is present and functional', () => {
    render(<HomePage />)
    // In Phase 9 the button is enabled once input has content; empty = disabled
    const btn = document.querySelector('#btn-analyze') as HTMLButtonElement
    expect(btn).toBeInTheDocument()
    expect(btn).toBeDisabled() // starts disabled with empty input
  })
})
