import { useState } from 'react'
import type { AnalyzeResponse } from '../types'
import TokensTab   from './TokensTab'
import ASTTab      from './ASTTab'
import AutomataTab from './AutomataTab'
import SecurityTab from './SecurityTab'
import TestRegexTab from './TestRegexTab'
import StatsPanel  from './StatsPanel'

type TabId = 'tokens' | 'ast' | 'automata' | 'security' | 'test'

const TABS: { id: TabId; label: string }[] = [
  { id: 'tokens',   label: 'Tokens' },
  { id: 'ast',      label: 'AST' },
  { id: 'automata', label: 'Automata' },
  { id: 'security', label: 'Security' },
  { id: 'test',     label: 'Test Regex' },
]

interface Props {
  result: AnalyzeResponse
  regex: string
}

export default function ResultsDashboard({ result, regex }: Props) {
  const [activeTab, setActiveTab] = useState<TabId>('tokens')

  const riskBadge: Record<string, string> = {
    HIGH:   'bg-red-500/20 text-red-300 border-red-500/40',
    MEDIUM: 'bg-amber-500/20 text-amber-300 border-amber-500/40',
    LOW:    'bg-emerald-500/20 text-emerald-300 border-emerald-500/40',
    NONE:   'bg-emerald-500/20 text-emerald-300 border-emerald-500/40',
  }

  const risk = result.security.overall_risk

  return (
    <div className="space-y-6" data-testid="results-dashboard">
      {/* Header bar */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="font-mono text-brand-300 bg-brand-500/10 border border-brand-500/20 px-3 py-1 rounded-lg text-sm">
            {regex}
          </span>
          <span className={`px-2 py-0.5 rounded text-xs font-bold border ${riskBadge[risk] ?? ''}`}>
            {risk} risk
          </span>
        </div>
        <p className="text-xs text-white/30">
          {result.stats.nfa_states} NFA states → {result.stats.dfa_states} DFA → {result.stats.minimized_dfa_states} min
          {result.stats.dfa_reduction_pct > 0 && (
            <span className="text-brand-400 ml-1">({result.stats.dfa_reduction_pct.toFixed(0)}% reduction)</span>
          )}
        </p>
      </div>

      {/* Diagnostics banner (semantic warnings/errors) */}
      {result.diagnostics.length > 0 && (
        <div className="bg-amber-500/10 border border-amber-500/30 rounded-xl px-4 py-3 space-y-1">
          {result.diagnostics.map((d, i) => (
            <p key={i} className="text-xs text-amber-300">
              <span className="font-mono bg-amber-500/20 px-1.5 py-0.5 rounded mr-2">{d.code}</span>
              {d.message}
              {d.location && <span className="text-amber-300/50 ml-1">(col {d.location.column})</span>}
            </p>
          ))}
        </div>
      )}

      <div className="grid lg:grid-cols-[1fr_260px] gap-6">
        {/* Main tabbed panel */}
        <div className="glass">
          {/* Tab bar */}
          <div className="flex overflow-x-auto border-b border-white/10 px-4 pt-4 gap-1 no-scrollbar"
               role="tablist">
            {TABS.map(tab => (
              <button
                key={tab.id}
                role="tab"
                aria-selected={activeTab === tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`px-3 py-2 rounded-t-lg text-xs font-medium whitespace-nowrap transition-all ${
                  activeTab === tab.id
                    ? 'bg-brand-600/20 text-brand-300 border-b-2 border-brand-500'
                    : 'text-white/40 hover:text-white/70'
                }`}
              >
                {tab.label}
                {tab.id === 'security' && risk !== 'NONE' && (
                  <span className={`ml-1.5 text-[9px] px-1 rounded ${
                    risk === 'HIGH' ? 'bg-red-500/30 text-red-300' : 'bg-amber-500/30 text-amber-300'
                  }`}>
                    {risk}
                  </span>
                )}
              </button>
            ))}
          </div>

          {/* Tab content */}
          <div className="p-5">
            {activeTab === 'tokens'   && <TokensTab   tokens={result.tokens} />}
            {activeTab === 'ast'      && <ASTTab      ast={result.ast} />}
            {activeTab === 'automata' && (
              <AutomataTab nfa={result.nfa} dfa={result.dfa} minimized_dfa={result.minimized_dfa} />
            )}
            {activeTab === 'security' && <SecurityTab  report={result.security} />}
            {activeTab === 'test'     && (
              <TestRegexTab regex={regex} minimizedDfa={result.minimized_dfa} />
            )}
          </div>
        </div>

        {/* Sidebar stats */}
        <div>
          <StatsPanel stats={result.stats} />
        </div>
      </div>
    </div>
  )
}
