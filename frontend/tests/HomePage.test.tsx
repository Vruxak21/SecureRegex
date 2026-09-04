/**
 * Phase 0 — Frontend smoke tests.
 *
 * These tests verify:
 *   1. The API client module is structured correctly (unit, no real network calls).
 *   2. The HomePage renders without crashing.
 *   3. The HomePage shows the "connecting" state on first render.
 *   4. The HomePage shows backend info when the API resolves.
 *
 * All network calls are mocked — these tests work with no backend running.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import HomePage from '../src/pages/HomePage'

// ── 1. API client unit tests ──────────────────────────────────────────────────

describe('API client', () => {
  it('exports an api object with health and info methods', async () => {
    const { api } = await import('../src/api/client')
    expect(typeof api.health).toBe('function')
    expect(typeof api.info).toBe('function')
  })
})

// ── 2. HomePage rendering ─────────────────────────────────────────────────────

const mockHealth = { status: 'ok', version: '0.1.0', app: 'SecureRegex' }
const mockInfo = {
  name: 'SecureRegex',
  version: '0.1.0',
  limits: {
    max_regex_length: 1000,
    max_input_length: 10000,
    max_nfa_states: 5000,
    max_dfa_states: 2000,
    max_computation_steps: 1000000,
  },
}

describe('HomePage', () => {
  beforeEach(() => {
    // Default: successful fetch
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockHealth,
    }))
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders the main heading', () => {
    render(<HomePage />)
    // Use heading role to avoid matching the disabled button which also has "Analyze Regex"
    const heading = screen.getByRole('heading', { level: 1 })
    expect(heading).toHaveTextContent(/Analyze Regex/i)
  })

  it('renders the "SecureRegex" brand name in nav', () => {
    render(<HomePage />)
    expect(screen.getByText('SecureRegex')).toBeInTheDocument()
  })

  it('shows "Connecting" status on initial render', () => {
    render(<HomePage />)
    expect(screen.getByText(/connecting/i)).toBeInTheDocument()
  })

  it('shows "Backend online" after health check resolves', async () => {
    // Mock both /health and /api/v1/info calls
    vi.stubGlobal('fetch', vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => mockHealth })
      .mockResolvedValueOnce({ ok: true, json: async () => mockInfo }),
    )

    render(<HomePage />)
    await waitFor(() =>
      expect(screen.getByText(/backend online/i)).toBeInTheDocument()
    )
  })

  it('shows error state when backend is unreachable', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('Connection refused')))

    render(<HomePage />)
    await waitFor(() =>
      expect(screen.getByText(/backend unreachable/i)).toBeInTheDocument()
    )
  })

  it('renders all 9 pipeline steps', () => {
    render(<HomePage />)
    const steps = ['Lexer', 'Parser', 'AST', 'Semantic', 'NFA', 'DFA', 'Minimize', 'Security', 'Report']
    steps.forEach(step => {
      expect(screen.getByText(step)).toBeInTheDocument()
    })
  })

  it('renders the 6 feature cards', () => {
    render(<HomePage />)
    // "Hand-written Compiler" also appears in the footer, so use getAllByText
    expect(screen.getAllByText(/Hand-written Compiler/i).length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText(/ReDoS Detection/i)).toBeInTheDocument()
    expect(screen.getByText(/Automata Visualizer/i)).toBeInTheDocument()
    expect(screen.getByText(/DFA Minimisation/i)).toBeInTheDocument()
    expect(screen.getByText(/JSON Reports/i)).toBeInTheDocument()
    expect(screen.getByText(/Docker-first/i)).toBeInTheDocument()
  })

  it('Analyze button is disabled with empty input', () => {
    render(<HomePage />)
    const btn = document.querySelector('#btn-analyze') as HTMLButtonElement
    expect(btn).toBeDisabled()
  })
})
