import type { SecurityReport } from '../types'

export default function SecurityTab({ report }: { report: SecurityReport }) {
  const high = report.overall_risk === 'HIGH'
  return <div>
    <div className={`risk-box ${high ? 'high' : ''}`}><strong>Overall Risk: {report.overall_risk}</strong><p style={{ margin: '6px 0 0', fontSize: 13 }}>These checks look for structures that can cause excessive work in backtracking regex engines.</p></div>
    {report.findings.length ? <div>{report.findings.map(f => <article className="finding" key={f.rule_id}><span className="token-badge"><span>{f.rule_id}</span> · {f.risk_level}</span><h3>{f.title}</h3><p>{f.reason}</p><details><summary className="subtle">Read explanation and recommendation</summary><p>{f.explanation}</p><p><strong>Recommendation:</strong> {f.recommendation}</p></details></article>)}</div> : <p className="subtle" style={{ marginTop: 20 }}>This pattern is structurally straightforward.</p>}
    <p className="subtle" style={{ marginTop: 20 }}>{report.caveat}</p>
  </div>
}
