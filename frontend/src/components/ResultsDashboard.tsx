import { useState } from 'react'
import type { AnalyzeResponse } from '../types'
import TokensTab from './TokensTab'
import ASTTab from './ASTTab'
import AutomataTab from './AutomataTab'
import SecurityTab from './SecurityTab'
import TestRegexTab from './TestRegexTab'
import StatsPanel from './StatsPanel'

type TabId = 'tokens' | 'ast' | 'automata' | 'security' | 'test'
const TABS: { id: TabId; label: string }[] = [
  { id: 'tokens', label: 'Tokens' }, { id: 'ast', label: 'AST' },
  { id: 'automata', label: 'Automata' }, { id: 'security', label: 'Security notes' },
  { id: 'test', label: 'Test Regex' },
]

export default function ResultsDashboard({ result, regex }: { result: AnalyzeResponse; regex: string }) {
  const [activeTab, setActiveTab] = useState<TabId>('tokens')
  const risk = result.security.overall_risk
  return (
    <div className="results-dashboard" data-testid="results-dashboard">
      <div className="result-heading">
        <div><div className="eyebrow">Analysis complete</div><h2>What the compiler found</h2><span className="pattern-chip">{regex}</span></div>
        <div className="result-summary">{result.stats.nfa_states} NFA states → {result.stats.dfa_states} DFA states → {result.stats.minimized_dfa_states} minimized<br /><strong className={risk === 'HIGH' ? 'error-text' : ''}>{risk} risk</strong></div>
      </div>
      {result.diagnostics.length > 0 && <div className="alert">{result.diagnostics.map(d => <div key={d.code}><strong>{d.code}</strong> {d.message}</div>)}</div>}
      <div className="results-grid">
        <div className="study-panel">
          <div className="study-tabs" role="tablist">
            {TABS.map(tab => <button key={tab.id} role="tab" aria-selected={activeTab === tab.id} className={`study-tab ${activeTab === tab.id ? 'active' : ''}`} onClick={() => setActiveTab(tab.id)}>{tab.label}{tab.id === 'security' && risk !== 'NONE' ? ` · ${risk}` : ''}</button>)}
          </div>
          <div className="study-content">
            {activeTab === 'tokens' && <TokensTab tokens={result.tokens} />}
            {activeTab === 'ast' && <ASTTab ast={result.ast} />}
            {activeTab === 'automata' && <AutomataTab nfa={result.nfa} dfa={result.dfa} minimized_dfa={result.minimized_dfa} />}
            {activeTab === 'security' && <SecurityTab report={result.security} />}
            {activeTab === 'test' && <TestRegexTab regex={regex} minimizedDfa={result.minimized_dfa} />}
          </div>
        </div>
        <StatsPanel stats={result.stats} />
      </div>
    </div>
  )
}
