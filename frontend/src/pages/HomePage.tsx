import { useEffect, useRef, useState } from 'react'
import { api, extractErrorMessage } from '../api/client'
import type { AnalyzeResponse, HealthResponse, InfoResponse } from '../types'
import ResultsDashboard from '../components/ResultsDashboard'

// ── Constants ────────────────────────────────────────────────────────────────

const EXAMPLE_PATTERNS = [
  { label: '(a|b)*abb', desc: 'Safe — canonical DFA example' },
  { label: '(a+)+',     desc: 'Dangerous — nested quantifiers' },
  { label: '(a|aa)+',   desc: 'Dangerous — overlapping alternation' },
  { label: '[a-z]+',    desc: 'Character class repetition' },
  { label: 'ab|cb',     desc: '5→3 state minimization' },
  { label: '(a?)+',     desc: 'Nullable repetition' },
]

// ── Sub-components ────────────────────────────────────────────────────────────

type ConnectionStatus = 'connecting' | 'ok' | 'error'

function StatusDot({ status }: { status: ConnectionStatus }) {
  const classes: Record<ConnectionStatus, string> = {
    connecting: 'status-loading animate-pulse',
    ok: 'status-ok',
    error: 'status-error',
  }
  const labels: Record<ConnectionStatus, string> = {
    connecting: '⟳ Connecting…',
    ok: '✓ Backend online',
    error: '✗ Backend unreachable',
  }
  return <span className={classes[status]}>{labels[status]}</span>
}

function PipelineStep({ step, label, active }: { step: number; label: string; active?: boolean }) {
  return (
    <div className={`flex flex-col items-center gap-2 ${active ? 'opacity-100' : 'opacity-40'}`}>
      <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold border
        ${active
          ? 'bg-brand-600 border-brand-400 text-white shadow-lg shadow-brand-500/40'
          : 'bg-surface-700 border-white/10 text-white/40'
        }`}>
        {step}
      </div>
      <span className="text-[10px] text-white/50 text-center max-w-[60px] leading-tight">{label}</span>
    </div>
  )
}

function FeatureCard({ icon, title, description }: { icon: string; title: string; description: string }) {
  return (
    <div className="glass p-6 flex flex-col gap-3 hover:border-brand-500/40 transition-all duration-300 hover:-translate-y-1 hover:shadow-xl hover:shadow-brand-500/10 group">
      <span className="text-3xl group-hover:scale-110 transition-transform duration-200">{icon}</span>
      <h3 className="font-semibold text-white text-sm">{title}</h3>
      <p className="text-white/50 text-xs leading-relaxed">{description}</p>
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function HomePage() {
  // Backend status
  const [health, setHealth]   = useState<HealthResponse | null>(null)
  const [info, setInfo]       = useState<InfoResponse | null>(null)
  const [status, setStatus]   = useState<ConnectionStatus>('connecting')
  const [connErr, setConnErr] = useState('')

  // Analyzer
  const [regex, setRegex]         = useState('')
  const [loading, setLoading]     = useState(false)
  const [result, setResult]       = useState<AnalyzeResponse | null>(null)
  const [analyzeErr, setAnalyzeErr] = useState('')
  const [errCol, setErrCol]       = useState<number | null>(null)

  const inputRef  = useRef<HTMLInputElement>(null)
  const resultRef = useRef<HTMLDivElement>(null)

  // Backend health check
  useEffect(() => {
    let cancelled = false
    async function check() {
      try {
        const [h, i] = await Promise.all([api.health(), api.info()])
        if (cancelled) return
        setHealth(h)
        setInfo(i)
        setStatus('ok')
      } catch (e: unknown) {
        if (cancelled) return
        setStatus('error')
        setConnErr((e as { message?: string })?.message ?? 'Unknown error')
      }
    }
    check()
    return () => { cancelled = true }
  }, [])

  const pipelineSteps = ['Lexer', 'Parser', 'AST', 'Semantic', 'NFA', 'DFA', 'Minimize', 'Security', 'Report']

  // ── Analyze handler ───────────────────────────────────────────────────────

  async function handleAnalyze() {
    const trimmed = regex.trim()
    if (!trimmed) return
    setLoading(true)
    setAnalyzeErr('')
    setErrCol(null)
    setResult(null)
    try {
      const r = await api.analyze(trimmed)
      setResult(r)
      // Scroll to results
      setTimeout(() => resultRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 80)
    } catch (e: unknown) {
      const msg = extractErrorMessage(e)
      setAnalyzeErr(msg)
      // Extract column for input highlighting
      const col = (e as { position?: { column?: number } })?.position?.column ?? null
      setErrCol(col)
    } finally {
      setLoading(false)
    }
  }

  function handleClear() {
    setRegex('')
    setResult(null)
    setAnalyzeErr('')
    setErrCol(null)
    inputRef.current?.focus()
  }

  function loadExample(pattern: string) {
    setRegex(pattern)
    setResult(null)
    setAnalyzeErr('')
    setErrCol(null)
    inputRef.current?.focus()
  }

  const canAnalyze = regex.trim().length > 0 && !loading

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="min-h-screen bg-surface-900 relative overflow-x-hidden">
      {/* Background glow blobs */}
      <div className="pointer-events-none fixed inset-0 overflow-hidden">
        <div className="absolute -top-40 -left-40 w-96 h-96 bg-brand-600/20 rounded-full blur-3xl animate-pulse-slow" />
        <div className="absolute -top-20 right-0 w-80 h-80 bg-purple-600/15 rounded-full blur-3xl animate-pulse-slow [animation-delay:1s]" />
        <div className="absolute bottom-0 left-1/3 w-72 h-72 bg-brand-500/10 rounded-full blur-3xl animate-pulse-slow [animation-delay:2s]" />
      </div>

      {/* ── Nav ── */}
      <nav className="relative z-10 flex items-center justify-between px-6 py-4 border-b border-white/5">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-gradient-to-br from-brand-500 to-purple-600 rounded-lg flex items-center justify-center text-sm font-bold shadow-lg shadow-brand-500/30">
            S
          </div>
          <span className="font-bold text-white tracking-tight">SecureRegex</span>
          {health && <span className="text-xs text-white/30 font-mono">v{health.version}</span>}
        </div>
        <StatusDot status={status} />
      </nav>

      {/* ── Hero ── */}
      <section className="relative z-10 max-w-5xl mx-auto px-6 pt-16 pb-8 text-center animate-slide-up">
        <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-brand-500/10 border border-brand-500/20 text-brand-300 text-xs font-medium mb-6">
          <span className="w-1.5 h-1.5 rounded-full bg-brand-400 animate-pulse" />
          Compiler-based ReDoS Analyzer — Phase 9
        </div>
        <h1 className="text-5xl sm:text-6xl font-extrabold leading-tight mb-4">
          <span className="text-white">Analyze Regex</span>
          <br />
          <span className="text-gradient">Security &amp; Automata</span>
        </h1>
        <p className="text-white/50 text-lg max-w-2xl mx-auto leading-relaxed mb-8">
          Hand-written Lexer → Parser → NFA → DFA → Hopcroft Minimization → ReDoS Security Analysis.
          No regex libraries — pure compiler pipeline.
        </p>
      </section>

      {/* ── Analyzer card ── */}
      <section className="relative z-10 max-w-5xl mx-auto px-6 pb-10">
        <div className="glass p-6 space-y-4">
          {/* Input row */}
          <div className="space-y-2">
            <label htmlFor="regex-input" className="text-xs text-white/40 uppercase tracking-wider">
              Regular Expression
            </label>
            <div className="relative">
              <input
                id="regex-input"
                ref={inputRef}
                type="text"
                value={regex}
                onChange={e => setRegex(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && canAnalyze && handleAnalyze()}
                placeholder="e.g. (a|b)*abb"
                spellCheck={false}
                autoComplete="off"
                className={`w-full bg-surface-800 border rounded-xl px-4 py-3 text-white font-mono text-base
                           placeholder-white/20 focus:outline-none focus:ring-1 transition-all
                           ${analyzeErr
                             ? 'border-red-500/60 focus:border-red-500 focus:ring-red-500/30'
                             : 'border-white/10 focus:border-brand-500/50 focus:ring-brand-500/30'
                           }`}
              />
              {/* Error column indicator */}
              {errCol !== null && (
                <div className="absolute right-3 top-1/2 -translate-y-1/2 text-xs font-mono text-red-400 bg-red-500/10 px-2 py-0.5 rounded">
                  col {errCol}
                </div>
              )}
            </div>
          </div>

          {/* Error banner */}
          {analyzeErr && (
            <div
              role="alert"
              className="flex items-start gap-3 bg-red-500/10 border border-red-500/30 rounded-xl px-4 py-3"
            >
              <span className="text-red-400 text-lg mt-0.5 shrink-0">⚠</span>
              <p className="text-red-300 text-sm leading-relaxed">{analyzeErr}</p>
            </div>
          )}

          {/* Actions */}
          <div className="flex flex-wrap gap-3">
            <button
              id="btn-analyze"
              onClick={handleAnalyze}
              disabled={!canAnalyze}
              className="btn-primary disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-2"
            >
              {loading
                ? <><span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" /> Analyzing…</>
                : <><span>⚡</span> Analyze</>
              }
            </button>
            <button
              onClick={handleClear}
              disabled={!regex && !result}
              className="px-5 py-2.5 rounded-xl text-sm font-semibold border border-white/10 text-white/50
                         hover:text-white hover:border-white/20 transition-all disabled:opacity-30 disabled:cursor-not-allowed"
            >
              Clear
            </button>
            <a
              href="/docs"
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl font-semibold text-sm
                         border border-white/10 text-white/50 hover:text-white hover:border-white/20 transition-all"
            >
              📖 API Docs
            </a>
          </div>

          {/* Example patterns */}
          <div className="space-y-2 pt-2 border-t border-white/5">
            <p className="text-xs text-white/30 uppercase tracking-wider">Examples</p>
            <div className="flex flex-wrap gap-2">
              {EXAMPLE_PATTERNS.map(({ label, desc }) => (
                <button
                  key={label}
                  onClick={() => loadExample(label)}
                  title={desc}
                  className="px-3 py-1.5 rounded-lg text-xs font-mono border border-white/10 text-white/50
                             hover:text-white hover:border-brand-500/40 hover:bg-brand-500/10 transition-all"
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ── Results ── */}
      {result && (
        <section ref={resultRef} className="relative z-10 max-w-5xl mx-auto px-6 pb-16 animate-fade-in">
          <ResultsDashboard result={result} regex={regex.trim()} />
        </section>
      )}

      {/* ── Pipeline vis (shown when no results) ── */}
      {!result && (
        <>
          <section className="relative z-10 max-w-5xl mx-auto px-6 pb-16">
            <h2 className="text-white/40 text-xs font-semibold uppercase tracking-widest text-center mb-8">
              Compiler Pipeline
            </h2>
            <div className="glass p-8 flex flex-wrap justify-center items-start gap-4">
              {pipelineSteps.map((label, i) => (
                <div key={label} className="flex items-center gap-4">
                  <PipelineStep step={i + 1} label={label} active={status === 'ok'} />
                  {i < pipelineSteps.length - 1 && (
                    <div className={`w-8 h-px ${status === 'ok' ? 'bg-brand-600' : 'bg-white/10'} transition-colors duration-700`} />
                  )}
                </div>
              ))}
            </div>
          </section>

          {/* Backend status card */}
          <section className="relative z-10 max-w-5xl mx-auto px-6 pb-16 animate-fade-in">
            <div className="glass p-6">
              <h2 className="font-semibold text-white/70 text-xs uppercase tracking-widest mb-4">
                Backend Connection
              </h2>
              {status === 'connecting' && (
                <div className="flex items-center gap-3 text-white/40">
                  <div className="w-4 h-4 border-2 border-brand-400 border-t-transparent rounded-full animate-spin" />
                  <span className="text-sm">Pinging backend at <code className="text-brand-300">http://localhost:8000/health</code>…</span>
                </div>
              )}
              {status === 'ok' && health && info && (
                <div className="grid sm:grid-cols-2 gap-6">
                  <div>
                    <p className="text-xs text-white/30 font-mono mb-2">GET /health</p>
                    <pre className="code-block text-xs">{JSON.stringify(health, null, 2)}</pre>
                  </div>
                  <div>
                    <p className="text-xs text-white/30 font-mono mb-2">GET /api/v1/info → limits</p>
                    <pre className="code-block text-xs">{JSON.stringify(info.limits, null, 2)}</pre>
                  </div>
                </div>
              )}
              {status === 'error' && (
                <div className="flex flex-col gap-2">
                  <p className="text-red-300 text-sm">
                    Could not reach the backend. Make sure it is running on <code className="text-red-200">localhost:8000</code>.
                  </p>
                  {connErr && <pre className="code-block text-xs text-red-300/70">{connErr}</pre>}
                  <p className="text-white/30 text-xs">
                    Start with: <code className="text-white/50">cd backend &amp;&amp; uvicorn app.main:app --reload</code>
                  </p>
                </div>
              )}
            </div>
          </section>

          {/* Feature grid */}
          <section className="relative z-10 max-w-5xl mx-auto px-6 pb-24">
            <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
              <FeatureCard icon="🔬" title="Hand-written Compiler" description="Zero use of Python's re module. Pure lexer, parser, NFA, and DFA from scratch." />
              <FeatureCard icon="🛡️" title="ReDoS Detection" description="Heuristic analysis of ambiguous NFA paths and exponential backtracking patterns." />
              <FeatureCard icon="🌐" title="Automata Visualizer" description="Interactive NFA and DFA graphs rendered with React Flow — states, transitions, accepting nodes." />
              <FeatureCard icon="⚡" title="DFA Minimisation" description="Hopcroft's algorithm reduces state count for efficient real-time matching." />
              <FeatureCard icon="📊" title="JSON Reports" description="Structured analysis output: AST, NFA stats, DFA stats, security findings." />
              <FeatureCard icon="🐳" title="Docker-first" description="Single docker-compose up brings up the full stack: FastAPI backend + Vite frontend." />
            </div>
          </section>
        </>
      )}

      {/* ── Footer ── */}
      <footer className="relative z-10 border-t border-white/5 py-6 px-6 text-center">
        <p className="text-white/20 text-xs">
          SecureRegex — Academic project. Hand-written compiler pipeline. No paid APIs.
        </p>
      </footer>
    </div>
  )
}
