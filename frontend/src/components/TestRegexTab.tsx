import { useState } from 'react'
import { api, extractErrorMessage } from '../api/client'
import type { Automaton } from '../types'

interface Props {
  regex: string
  minimizedDfa: Automaton
}

export default function TestRegexTab({ regex, minimizedDfa }: Props) {
  const [input, setInput]     = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult]   = useState<{ matched: boolean; path: number[] } | null>(null)
  const [error, setError]     = useState('')

  async function handleTest() {
    if (!input && input !== '') return
    setLoading(true)
    setError('')
    setResult(null)
    try {
      const r = await api.test(regex, input)
      setResult(r)
    } catch (e) {
      setError(extractErrorMessage(e))
    } finally {
      setLoading(false)
    }
  }

  const accepting = new Set(minimizedDfa.accepting)

  return (
    <div className="space-y-5">
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
        <div className="space-y-4">
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

          {/* State path */}
          <div>
            <p className="text-xs text-white/30 uppercase tracking-wider mb-3">
              DFA State Path ({result.path.length} states visited)
            </p>
            <div className="flex flex-wrap items-center gap-2">
              {result.path.map((state, i) => (
                <div key={i} className="flex items-center gap-2">
                  <div className={`flex flex-col items-center`}>
                    <span className={`w-10 h-10 rounded-full flex items-center justify-center text-xs font-bold border-2 transition-all ${
                      accepting.has(state)
                        ? 'bg-emerald-500/30 border-emerald-400 text-emerald-200'
                        : state === minimizedDfa.start
                        ? 'bg-brand-500/30 border-brand-400 text-brand-200'
                        : 'bg-white/5 border-white/20 text-white/60'
                    }`}>
                      q{state}
                    </span>
                    {i < result.path.length - 1 && (
                      <span className="text-[9px] text-white/30 mt-0.5 font-mono">
                        {input[i] ?? ''}
                      </span>
                    )}
                  </div>
                  {i < result.path.length - 1 && (
                    <span className="text-white/20 text-lg mb-3">→</span>
                  )}
                </div>
              ))}
            </div>
            <div className="flex gap-4 mt-3">
              <span className="text-[10px] text-brand-300/50">■ start</span>
              <span className="text-[10px] text-emerald-300/50">■ accepting</span>
              <span className="text-[10px] text-white/20">■ normal</span>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
