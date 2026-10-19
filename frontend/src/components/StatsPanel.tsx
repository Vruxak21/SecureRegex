import type { PipelineStats } from '../types'

function Row({ label, value, accent }: { label: string; value: string | number; accent?: boolean }) {
  return <div className="stat-row"><span>{label}</span><span className={accent ? 'error-text' : ''}>{value}</span></div>
}

export default function StatsPanel({ stats }: { stats: PipelineStats }) {
  return <aside className="stats-panel"><h3>At a glance</h3>
    <Row label="Pattern length" value={`${stats.regex_length} chars`} /><Row label="Tokens" value={stats.token_count} />
    <Row label="AST nodes" value={stats.ast_node_count} /><Row label="NFA states" value={stats.nfa_states} />
    <Row label="NFA transitions" value={stats.nfa_transitions} /><Row label="DFA states" value={stats.dfa_states} />
    <Row label="DFA transitions" value={stats.dfa_transitions} /><Row label="Minimized states" value={stats.minimized_dfa_states} />
    <Row label="DFA reduction" value={`${stats.dfa_reduction_pct.toFixed(1)}%`} /><Row label="Security" value={stats.overall_security_risk} accent={stats.overall_security_risk === 'HIGH'} />
  </aside>
}
