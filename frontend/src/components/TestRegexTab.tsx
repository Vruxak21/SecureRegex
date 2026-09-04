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
    <div className="space-y-5">
      {/* Input row */}
      <div className="flex gap-3">
        <input
          id="test-input"
          type="text"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleTest()}
          placeholder="Type a string to test…"
          className="flex-1 bg-white/5 border border-white/10 rounded-xl px-4 py-2.5 text-white
                     placeholder-white/20 font-mono text-sm focus:outline-none focus:border-brand-500/50
                     focus:ring-1 focus:ring-brand-500/30 transition-all"
        />
        <button
          onClick={handleTest}
          disabled={loading}
          className="px-5 py-2.5 rounded-xl bg-brand-600 hover:bg-brand-500 text-white font-semibold
                     text-sm transition-all disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? '…' : 'Test'}
        </button>
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl px-4 py-3 text-red-300 text-sm">
          {error}
        </div>
      )}

      {result && (
        <div className="space-y-5">
          {/* Result badge */}
          <div className={`flex items-center gap-3 px-4 py-3 rounded-xl border ${
            result.matched
              ? 'bg-emerald-500/15 border-emerald-500/40 text-emerald-300'
              : 'bg-red-500/15 border-red-500/40 text-red-300'
          }`}>
            <span className="text-2xl">{result.matched ? '✅' : '❌'}</span>
            <div>
              <p className="font-bold text-sm">
                {result.matched ? 'ACCEPTED' : 'REJECTED'}
              </p>
              <p className="text-xs opacity-70">
                "{input || '<empty>'}" {result.matched ? 'matches' : 'does not match'} the pattern
              </p>
            </div>
          </div>

          {/* ── Traversal graph ── */}
          <div className="space-y-3">
            <div className="flex items-center justify-between flex-wrap gap-2">
              <p className="text-xs text-white/40 uppercase tracking-wider">
                DFA Traversal — Step {step + 1} / {maxStep + 1}
              </p>
              {/* Step-through controls */}
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setStep(0)}
                  disabled={step === 0}
                  className="px-2 py-1 text-xs rounded bg-white/5 border border-white/10
                             text-white/50 hover:text-white disabled:opacity-30 transition-all"
                  title="Reset to start"
                >⏮</button>
                <button
                  onClick={() => setStep(s => Math.max(0, s - 1))}
                  disabled={step === 0}
                  className="px-2 py-1 text-xs rounded bg-white/5 border border-white/10
                             text-white/50 hover:text-white disabled:opacity-30 transition-all"
                  title="Previous state"
                >◀</button>
                <button
                  onClick={() => setStep(s => Math.min(maxStep, s + 1))}
                  disabled={step === maxStep}
                  className="px-2 py-1 text-xs rounded bg-white/5 border border-white/10
                             text-white/50 hover:text-white disabled:opacity-30 transition-all"
                  title="Next state"
                >▶</button>
                <button
                  onClick={() => setStep(maxStep)}
                  disabled={step === maxStep}
                  className="px-2 py-1 text-xs rounded bg-white/5 border border-white/10
                             text-white/50 hover:text-white disabled:opacity-30 transition-all"
                  title="Jump to end"
                >⏭</button>
              </div>
            </div>

            {/* Current symbol consumed */}
            <div className="flex items-center gap-2 text-sm">
              <span className="text-white/30">State:</span>
              <span className="font-mono text-brand-300 font-bold">q{result.path[step]}</span>
              {step > 0 && step <= input.length && (
                <>
                  <span className="text-white/20 mx-1">via</span>
                  <span className="font-mono px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30">
                    '{input[step - 1]}'
                  </span>
                </>
              )}
              {step === 0 && <span className="text-white/30 text-xs">(start state)</span>}
              {accepting.has(result.path[step]) && (
                <span className="ml-2 px-2 py-0.5 rounded text-xs bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
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
