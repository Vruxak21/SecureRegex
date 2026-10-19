import { useState, useCallback } from 'react'
import { api, extractErrorMessage } from '../api/client'
import type { Automaton } from '../types'
import AutomataGraph from '../visualizations/AutomataGraph'

interface Props {
  regex: string
  minimizedDfa: Automaton
}

export default function TestRegexTab({ regex, minimizedDfa }: Props) {
  const [input,    setInput]   = useState('')
  const [loading,  setLoading] = useState(false)
  const [result,   setResult]  = useState<{ matched: boolean; path: number[] } | null>(null)
  const [error,    setError]   = useState('')
  // step-through traversal
  const [step,     setStep]    = useState<number>(0)

  const accepting = new Set(minimizedDfa.accepting)

  const handleTest = useCallback(async () => {
    setLoading(true)
    setError('')
    setResult(null)
    setStep(0)
    try {
      const r = await api.test(regex, input)
      setResult(r)
    } catch (e) {
      setError(extractErrorMessage(e))
    } finally {
      setLoading(false)
    }
  }, [regex, input])

  // Which states to highlight at current step:
  // show the path up to (and including) `step`
  const highlightedStates = result
    ? result.path.slice(0, step + 1)
    : []

  const maxStep = result ? result.path.length - 1 : 0

  return (
    <div className="test-workspace">
      {/* Input row */}
      <div className="regex-row">
        <input
          id="test-input"
          type="text"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleTest()}
          placeholder="Type a string to test…"
          className="regex-input"
        />
        <button
          onClick={handleTest}
          disabled={loading}
          className="btn-analyze"
        >
          {loading ? '…' : 'Test'}
        </button>
      </div>

      {error && (
        <div className="alert">
          {error}
        </div>
      )}

      {result && (
        <div className="test-workspace">
          {/* Result badge */}
          <div className={`risk-box ${result.matched ? '' : 'high'}`}>
            <span>{result.matched ? 'Accepted' : 'Rejected'}</span>
            <div>
              <p>
                {result.matched ? 'ACCEPTED' : 'REJECTED'}
              </p>
              <p className="subtle">
                "{input || '<empty>'}" {result.matched ? 'matches' : 'does not match'} the pattern
              </p>
            </div>
          </div>

          {/* ── Traversal graph ── */}
          <div className="space-y-3">
            <div className="automata-switch">
              <p className="subtle">
                DFA Traversal — Step {step + 1} / {maxStep + 1}
              </p>
              {/* Step-through controls */}
              <div className="view-toggle">
                <button
                  onClick={() => setStep(0)}
                  disabled={step === 0}
                  className="switch-button"
                  title="Reset to start"
                >⏮</button>
                <button
                  onClick={() => setStep(s => Math.max(0, s - 1))}
                  disabled={step === 0}
                  className="switch-button"
                  title="Previous state"
                >◀</button>
                <button
                  onClick={() => setStep(s => Math.min(maxStep, s + 1))}
                  disabled={step === maxStep}
                  className="switch-button"
                  title="Next state"
                >▶</button>
                <button
                  onClick={() => setStep(maxStep)}
                  disabled={step === maxStep}
                  className="switch-button"
                  title="Jump to end"
                >⏭</button>
              </div>
            </div>

            {/* Current symbol consumed */}
            <div className="subtle">
              <span>State: </span>
              <span className="mono"><strong>q{result.path[step]}</strong></span>
              {step > 0 && step <= input.length && (
                <>
                  <span> via </span>
                  <span className="token-badge">
                    '{input[step - 1]}'
                  </span>
                </>
              )}
              {step === 0 && <span> (start state)</span>}
              {accepting.has(result.path[step]) && (
                <span className="token-badge">
                  accepting ★
                </span>
              )}
            </div>

            {/* Interactive graph with highlighted path */}
            <AutomataGraph
              automaton={minimizedDfa}
              highlightedStates={highlightedStates}
              height={340}
            />

            {/* Linear path strip */}
            <div className="flex flex-wrap items-center gap-1.5">
              {result.path.map((state, i) => (
                <div key={i} className="flex items-center gap-1.5">
                  <button
                    onClick={() => setStep(i)}
                    className={`w-9 h-9 rounded-full flex items-center justify-center text-xs font-bold
                               border-2 font-mono transition-all ${
                      i === step
                        ? 'bg-indigo-500/40 border-indigo-400 text-indigo-200 shadow-[0_0_10px_2px_rgba(99,102,241,0.4)]'
                        : i < step
                        ? 'bg-brand-600/30 border-brand-500/60 text-brand-300'
                        : accepting.has(state)
                        ? 'bg-emerald-900/40 border-emerald-500/40 text-emerald-300/60'
                        : 'bg-white/5 border-white/10 text-white/30'
                    }`}
                    title={`Jump to step ${i + 1}: q${state}`}
                  >
                    q{state}
                  </button>
                  {i < result.path.length - 1 && (
                    <div className="flex flex-col items-center">
                      <span className="text-[10px] font-mono text-amber-400/70">
                        {input[i] ?? ''}
                      </span>
                      <span className="text-white/20">→</span>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
