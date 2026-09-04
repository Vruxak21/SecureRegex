import type { PipelineStats } from '../types'

const RISK_COLORS: Record<string, string> = {
  HIGH:   'text-red-400',
  MEDIUM: 'text-amber-400',
  LOW:    'text-emerald-400',
  NONE:   'text-emerald-400',
}

function StatRow({ label, value, highlight }: { label: string; value: string | number; highlight?: string }) {
  return (
    <div className="flex items-center justify-between py-2 border-b border-white/5 last:border-0">
      <span className="text-xs text-white/40">{label}</span>
      <span className={`text-sm font-mono font-semibold ${highlight ?? 'text-white/80'}`}>
        {value}
      </span>
    </div>
  )
}

export default function StatsPanel({ stats }: { stats: PipelineStats }) {
  return (
    <div className="bg-white/3 border border-white/8 rounded-xl p-4 space-y-1">
      <p className="text-xs text-white/30 uppercase tracking-wider mb-3">Pipeline Statistics</p>
      <StatRow label="Regex length"          value={`${stats.regex_length} chars`} />
      <StatRow label="Tokens"                value={stats.token_count} />
      <StatRow label="AST nodes"             value={stats.ast_node_count} />
      <StatRow label="NFA states"            value={stats.nfa_states} />
      <StatRow label="NFA transitions"       value={stats.nfa_transitions} />
      <StatRow label="DFA states"            value={stats.dfa_states} />
      <StatRow label="DFA transitions"       value={stats.dfa_transitions} />
      <StatRow label="Minimized DFA states"  value={stats.minimized_dfa_states} />
      <StatRow
        label="DFA reduction"
        value={`${stats.dfa_reduction_pct.toFixed(1)}%`}
        highlight={stats.dfa_reduction_pct > 0 ? 'text-brand-300' : 'text-white/80'}
      />
      <StatRow
        label="Security risk"
        value={stats.overall_security_risk}
        highlight={RISK_COLORS[stats.overall_security_risk] ?? 'text-white/80'}
      />
    </div>
  )
}
