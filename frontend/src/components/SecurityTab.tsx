import type { SecurityReport } from '../types'

const RISK_COLORS: Record<string, string> = {
  HIGH:   'text-red-300 bg-red-500/20 border-red-500/40',
  MEDIUM: 'text-amber-300 bg-amber-500/20 border-amber-500/40',
  LOW:    'text-emerald-300 bg-emerald-500/20 border-emerald-500/40',
  NONE:   'text-emerald-300 bg-emerald-500/20 border-emerald-500/40',
}

const RISK_ICONS: Record<string, string> = {
  HIGH: '🔴', MEDIUM: '🟡', LOW: '🟢', NONE: '✅',
}

export default function SecurityTab({ report }: { report: SecurityReport }) {
  return (
    <div className="space-y-5">
      {/* Overall risk banner */}
      <div className={`flex items-center gap-3 px-4 py-3 rounded-xl border ${RISK_COLORS[report.overall_risk]}`}>
        <span className="text-2xl">{RISK_ICONS[report.overall_risk]}</span>
        <div>
          <p className="font-bold text-sm">Overall Risk: {report.overall_risk}</p>
          {report.overall_risk === 'NONE' && (
            <p className="text-xs opacity-70">No ReDoS risk indicators detected in this pattern.</p>
          )}
        </div>
      </div>

      {/* Findings */}
      {report.findings.length > 0 ? (
        <div className="space-y-3">
          {report.findings.map((f, i) => (
            <div key={i} className="bg-white/3 border border-white/8 rounded-xl p-4 space-y-2">
              <div className="flex items-center justify-between flex-wrap gap-2">
                <div className="flex items-center gap-2">
                  <span className="px-2 py-0.5 rounded text-xs font-mono bg-white/10 text-white/50 border border-white/10">
                    {f.rule_id}
                  </span>
                  <span className={`px-2 py-0.5 rounded text-xs font-bold border ${RISK_COLORS[f.risk_level]}`}>
                    {f.risk_level}
                  </span>
                </div>
                {f.location && (
                  <span className="text-xs font-mono text-white/30">col {f.location.start}</span>
                )}
              </div>
              <p className="font-semibold text-white/90 text-sm">{f.title}</p>
              <p className="text-xs text-white/50 leading-relaxed">{f.reason}</p>
              <details className="group">
                <summary className="text-xs text-brand-400 cursor-pointer hover:text-brand-300 transition-colors">
                  ▶ Explanation &amp; Recommendation
                </summary>
                <div className="mt-2 space-y-2 pl-3 border-l border-white/10">
                  <p className="text-xs text-white/50 leading-relaxed">{f.explanation}</p>
                  <p className="text-xs text-emerald-400/70 leading-relaxed">
                    <span className="text-emerald-400 font-medium">Fix: </span>{f.recommendation}
                  </p>
                </div>
              </details>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-sm text-white/40 text-center py-6">No findings — pattern is structurally safe.</p>
      )}

      {/* Caveat */}
      <div className="bg-white/3 border border-white/8 rounded-xl p-4">
        <p className="text-xs text-white/30 leading-relaxed">
          <span className="text-white/50 font-medium">ℹ️ Note: </span>{report.caveat}
        </p>
      </div>
    </div>
  )
}
