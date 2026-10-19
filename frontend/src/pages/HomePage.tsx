import { useEffect, useRef, useState } from 'react'
import { api, extractErrorMessage } from '../api/client'
import type { AnalyzeResponse, HealthResponse, InfoResponse } from '../types'
import ResultsDashboard from '../components/ResultsDashboard'

const EXAMPLE_PATTERNS = [
  { label: '(a|b)*abb', desc: 'A complete compiler example' },
  { label: '(a+)+', desc: 'Nested quantifiers' },
  { label: '(a|aa)+', desc: 'Overlapping alternation' },
  { label: '[a-z]+', desc: 'Character class repetition' },
  { label: 'ab|cb', desc: 'A minimization example' },
  { label: '(a?)+', desc: 'Nullable repetition' },
]

const PIPELINE_STEPS = ['Lexer', 'Parser', 'AST', 'Semantic', 'NFA', 'DFA', 'Minimize', 'Security', 'Report']

type ConnectionStatus = 'connecting' | 'ok' | 'error'

function Status({ status }: { status: ConnectionStatus }) {
  const label = status === 'connecting' ? 'Connecting' : status === 'ok' ? 'Backend online' : 'Backend unreachable'
  return <span className={`connection ${status}`}><span className="connection-dot" />{label}</span>
}

export default function HomePage() {
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [, setInfo] = useState<InfoResponse | null>(null)
  const [status, setStatus] = useState<ConnectionStatus>('connecting')
  const [connErr, setConnErr] = useState('')
  const [regex, setRegex] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<AnalyzeResponse | null>(null)
  const [analyzeErr, setAnalyzeErr] = useState('')
  const [errCol, setErrCol] = useState<number | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const resultRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    let cancelled = false
    Promise.all([api.health(), api.info()])
      .then(([healthResponse, infoResponse]) => {
        if (cancelled) return
        setHealth(healthResponse)
        setInfo(infoResponse)
        setStatus('ok')
      })
      .catch((error: unknown) => {
        if (cancelled) return
        setStatus('error')
        setConnErr((error as { message?: string })?.message ?? 'Connection refused')
      })
    return () => { cancelled = true }
  }, [])

  async function handleAnalyze() {
    const trimmed = regex.trim()
    if (!trimmed) return
    setLoading(true)
    setAnalyzeErr('')
    setErrCol(null)
    setResult(null)
    try {
      const response = await api.analyze(trimmed)
      setResult(response)
      setTimeout(() => resultRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 80)
    } catch (error: unknown) {
      setAnalyzeErr(extractErrorMessage(error))
      setErrCol((error as { position?: { column?: number } })?.position?.column ?? null)
    } finally {
      setLoading(false)
    }
  }

  function clearWorkspace() {
    setRegex('')
    setResult(null)
    setAnalyzeErr('')
    setErrCol(null)
    inputRef.current?.focus()
  }

  function useExample(pattern: string) {
    setRegex(pattern)
    setResult(null)
    setAnalyzeErr('')
    setErrCol(null)
    inputRef.current?.focus()
  }

  const canAnalyze = regex.trim().length > 0 && !loading

  return (
    <div className="learning-shell">
      <header className="site-header">
        <div className="header-inner">
          <a className="brand" href="/" aria-label="SecureRegex home">
            <span className="brand-mark">S</span>
            <span className="brand-name">SecureRegex</span>
            <span className="brand-subtitle">Regex laboratory</span>
          </a>
          <div className="connection-wrap">
            <Status status={status} />
            {health && <span className="brand-subtitle">v{health.version}</span>}
          </div>
        </div>
      </header>

      <main className="page-wrap">
        <section className="hero">
          <div>
            <div className="eyebrow">A visual lesson in regular expressions</div>
            <h1>Analyze Regex.<br /><em>See the machine.</em></h1>
            <p className="hero-copy">
              Turn a regular expression into its tokens, syntax tree, automata,
              and security notes. A clear, step-by-step workspace for learning
              how regex engines are built.
            </p>
          </div>
          <aside className="lesson-note">
            <strong>How to use this lab</strong>
            Start with an example or type your own pattern. The compiler trail
            below the editor shows what each stage contributes.
          </aside>
        </section>

        <section className="analyzer-board" aria-label="Regex analyzer">
          <label className="board-label" htmlFor="regex-input">Your regular expression</label>
          <div className="regex-row">
            <div className="regex-field" style={{ position: 'relative', flex: 1 }}>
              <input
                id="regex-input"
                ref={inputRef}
                className={`regex-input ${analyzeErr ? 'error' : ''}`}
                value={regex}
                onChange={event => setRegex(event.target.value)}
                onKeyDown={event => event.key === 'Enter' && canAnalyze && handleAnalyze()}
                placeholder="Try (a|b)*abb"
                spellCheck={false}
                autoComplete="off"
              />
              {errCol !== null && <span className="mono error-text" style={{ position: 'absolute', right: 12, top: 16, fontSize: 11 }}>column {errCol}</span>}
            </div>
            <button id="btn-analyze" className="btn-analyze" onClick={handleAnalyze} disabled={!canAnalyze}>
              {loading ? 'Analyzing…' : 'Analyze pattern'}
            </button>
          </div>
          {analyzeErr && <div className="alert" role="alert">{analyzeErr}</div>}
          <div className="examples">
            <span>Try a lesson:</span>
            {EXAMPLE_PATTERNS.map(example => (
              <button key={example.label} className="example-chip" title={example.desc} onClick={() => useExample(example.label)}>
                {example.label}
              </button>
            ))}
            <button className="btn-quiet" style={{ marginLeft: 'auto' }} onClick={clearWorkspace} disabled={!regex && !result}>Clear</button>
          </div>
        </section>

        {result ? (
          <section ref={resultRef} className="results-shell">
            <ResultsDashboard result={result} regex={regex.trim()} />
          </section>
        ) : (
          <>
            <section className="pipeline">
              <h2 className="section-title">The compiler trail</h2>
              <div className="pipeline-track">
                {PIPELINE_STEPS.map(step => <div className="pipeline-step" key={step}>{step}</div>)}
              </div>
            </section>
            <section className="feature-grid" aria-label="What you can study">
              <article className="feature-card"><h3>Hand-written compiler</h3><p>Follow a pattern from characters to a working automaton without hiding the interesting steps.</p></article>
              <article className="feature-card"><h3>ReDoS detection</h3><p>Learn why nested quantifiers and overlapping branches can be risky in backtracking engines.</p></article>
              <article className="feature-card"><h3>Automata visualizer</h3><p>Compare epsilon-NFA, DFA, and minimized DFA diagrams side by side in one study panel.</p></article>
              <article className="feature-card"><h3>DFA Minimisation</h3><p>See equivalent states merge while the recognized language stays the same.</p></article>
              <article className="feature-card"><h3>JSON Reports</h3><p>Inspect tokens, syntax nodes, transitions, and findings in a readable format.</p></article>
              <article className="feature-card"><h3>Docker-first</h3><p>Your classroom experiments stay on the local app and use no paid services.</p></article>
            </section>
            <section className="footer">
              {status === 'error'
                ? <>The workspace cannot reach the compiler at <code>localhost:8000</code>. Start the backend, then refresh. {connErr && <span>{connErr}</span>}</>
                : <>The compiler is ready when the status indicator says <strong>Backend online</strong>.</>}
            </section>
          </>
        )}
      </main>
    </div>
  )
}
