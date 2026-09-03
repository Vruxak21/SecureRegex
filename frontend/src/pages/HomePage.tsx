import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { HealthResponse, InfoResponse } from '../types'

// ─── Status indicator ────────────────────────────────────────────────────────

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

// ─── Feature card ─────────────────────────────────────────────────────────────

function FeatureCard({
  icon,
  title,
  description,
}: {
  icon: string
  title: string
  description: string
}) {
  return (
    <div className="glass p-6 flex flex-col gap-3 hover:border-brand-500/40 transition-all duration-300 hover:-translate-y-1 hover:shadow-xl hover:shadow-brand-500/10 group">
      <span className="text-3xl group-hover:scale-110 transition-transform duration-200">
        {icon}
      </span>
      <h3 className="font-semibold text-white text-sm">{title}</h3>
      <p className="text-white/50 text-xs leading-relaxed">{description}</p>
    </div>
  )
}

// ─── Pipeline step ───────────────────────────────────────────────────────────

function PipelineStep({ step, label, active }: { step: number; label: string; active?: boolean }) {
  return (
    <div className={`flex flex-col items-center gap-2 ${active ? 'opacity-100' : 'opacity-40'}`}>
      <div
        className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold border
          ${active
            ? 'bg-brand-600 border-brand-400 text-white shadow-lg shadow-brand-500/40'
            : 'bg-surface-700 border-white/10 text-white/40'
          }`}
      >
        {step}
      </div>
      <span className="text-[10px] text-white/50 text-center max-w-[60px] leading-tight">{label}</span>
    </div>
  )
}

// ─── Page ────────────────────────────────────────────────────────────────────

export default function HomePage() {
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [info, setInfo] = useState<InfoResponse | null>(null)
  const [status, setStatus] = useState<ConnectionStatus>('connecting')
  const [errorMsg, setErrorMsg] = useState<string>('')

  useEffect(() => {
    let cancelled = false

    async function checkBackend() {
      try {
        const [h, i] = await Promise.all([api.health(), api.info()])
        if (cancelled) return
        setHealth(h)
        setInfo(i)
        setStatus('ok')
      } catch (e: unknown) {
        if (cancelled) return
        setStatus('error')
        const err = e as { message?: string }
        setErrorMsg(err?.message ?? 'Unknown error')
      }
    }

    checkBackend()
    return () => { cancelled = true }
  }, [])

  const pipelineSteps = [
    'Lexer', 'Parser', 'AST', 'Semantic', 'NFA',
    'DFA', 'Minimize', 'Security', 'Report',
  ]

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
          {health && (
            <span className="text-xs text-white/30 font-mono">v{health.version}</span>
          )}
        </div>
        <StatusDot status={status} />
      </nav>

      {/* ── Hero ── */}
      <section className="relative z-10 max-w-5xl mx-auto px-6 pt-24 pb-16 text-center animate-slide-up">
        <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-brand-500/10 border border-brand-500/20 text-brand-300 text-xs font-medium mb-6">
          <span className="w-1.5 h-1.5 rounded-full bg-brand-400 animate-pulse" />
          Academic + Portfolio Project — Phase 0
        </div>

        <h1 className="text-5xl sm:text-6xl font-extrabold leading-tight mb-6">
          <span className="text-white">Analyze Regex</span>
          <br />
          <span className="text-gradient">Security &amp; Automata</span>
        </h1>

        <p className="text-white/50 text-lg max-w-2xl mx-auto leading-relaxed mb-10">
          A compiler-built pipeline: hand-written Lexer → Parser → NFA → DFA → Security
          Analyzer. Detects ReDoS vulnerabilities and visualises automata in real time.
        </p>

        <div className="flex flex-wrap items-center justify-center gap-4">
          <button
            id="btn-analyze"
            className="btn-primary opacity-50 cursor-not-allowed"
            disabled
            title="Coming in Phase 1+"
          >
            <span>⚡</span> Analyze Regex
          </button>
          <a
            id="link-docs"
            href="/docs"
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl font-semibold text-sm
                       border border-white/10 text-white/70 hover:text-white hover:border-white/20
                       transition-all duration-200"
          >
            <span>📖</span> View API Docs
          </a>
        </div>
      </section>

      {/* ── Backend status card ── */}
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
              {/* Health payload */}
              <div>
                <p className="text-xs text-white/30 font-mono mb-2">GET /health</p>
                <pre className="code-block text-xs">
{JSON.stringify(health, null, 2)}
                </pre>
              </div>
              {/* Info / limits */}
              <div>
                <p className="text-xs text-white/30 font-mono mb-2">GET /api/v1/info → limits</p>
                <pre className="code-block text-xs">
{JSON.stringify(info.limits, null, 2)}
                </pre>
              </div>
            </div>
          )}

          {status === 'error' && (
            <div className="flex flex-col gap-2">
              <p className="text-red-300 text-sm">
                Could not reach the backend. Make sure it is running on <code className="text-red-200">localhost:8000</code>.
              </p>
              {errorMsg && (
                <pre className="code-block text-xs text-red-300/70">{errorMsg}</pre>
              )}
              <p className="text-white/30 text-xs">
                Start with: <code className="text-white/50">cd backend && uvicorn app.main:app --reload</code>
              </p>
            </div>
          )}
        </div>
      </section>

      {/* ── Pipeline visualisation ── */}
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

      {/* ── Feature grid ── */}
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

      {/* ── Footer ── */}
      <footer className="relative z-10 border-t border-white/5 py-6 px-6 text-center">
        <p className="text-white/20 text-xs">
          SecureRegex — Academic project. Hand-written compiler pipeline. No paid APIs.
        </p>
      </footer>
    </div>
  )
}
