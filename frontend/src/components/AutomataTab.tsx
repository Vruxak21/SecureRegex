import { useState } from 'react'
import type { Automaton } from '../types'
import AutomataGraph from '../visualizations/AutomataGraph'

function AutomataTable({ automaton }: { automaton: Automaton }) {
  return (
    <div className="space-y-4">
      {/* Summary row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: 'States',    value: automaton.states.length },
          { label: 'Alphabet',  value: automaton.alphabet.join(', ') || '∅' },
          { label: 'Start',     value: `q${automaton.start}` },
          { label: 'Accepting', value: automaton.accepting.map(s => `q${s}`).join(', ') || '∅' },
        ].map(({ label, value }) => (
          <div key={label} className="feature-card" style={{ minHeight: 'auto', padding: 14 }}>
            <p className="subtle" style={{ margin: 0 }}>{label}</p>
            <p className="mono" style={{ margin: '5px 0 0' }}>{String(value)}</p>
          </div>
        ))}
      </div>

      {/* Transition table */}
      <div>
        <p className="subtle" style={{ marginBottom: 8 }}>
          Transitions ({automaton.transitions.length})
        </p>
        <div className="overflow-x-auto max-h-52">
          <table className="light-table">
            <thead>
              <tr>
                <th>From</th><th>Symbol</th><th>To</th>
              </tr>
            </thead>
            <tbody>
              {automaton.transitions.map((t, i) => (
                <tr key={i}>
                  <td className="mono">
                    {automaton.accepting.includes(t.from) ? '★ ' : ''}q{t.from}
                  </td>
                  <td className="mono">
                    {t.symbol === 'ε'
                      ? <span>{t.symbol}</span>
                      : <span>{t.symbol}</span>}
                  </td>
                  <td className="mono">
                    {automaton.accepting.includes(t.to) ? '★ ' : ''}q{t.to}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="subtle" style={{ fontSize: 11 }}>★ = accepting state</p>
      </div>
    </div>
  )
}

export default function AutomataTab({
  nfa, dfa, minimized_dfa,
}: {
  nfa: Automaton
  dfa: Automaton
  minimized_dfa: Automaton
}) {
  const [active, setActive] = useState<'nfa' | 'dfa' | 'min'>('nfa')
  const [view,   setView]   = useState<'graph' | 'table'>('graph')

  const tabs = [
    { id: 'nfa' as const, label: 'NFA',     data: nfa },
    { id: 'dfa' as const, label: 'DFA',     data: dfa },
    { id: 'min' as const, label: 'Min DFA', data: minimized_dfa },
  ]
  const current = tabs.find(t => t.id === active)!

  return (
    <div className="space-y-4">
      {/* Automaton type tabs */}
      <div className="automata-switch">
        <div className="switch-group">
          {tabs.map(t => (
            <button
              key={t.id}
              onClick={() => setActive(t.id)}
              className={`switch-button ${active === t.id ? 'active' : ''}`}
            >
              {t.label}
              <span className="ml-1.5 text-[10px] opacity-60">{t.data.states.length}q</span>
            </button>
          ))}
        </div>

        {/* Graph / Table toggle */}
        <div className="view-toggle">
          {(['graph', 'table'] as const).map(v => (
            <button
              key={v}
              onClick={() => setView(v)}
              className={`switch-button ${view === v ? 'active' : ''}`}
            >
              {v === 'graph' ? '⬡ Graph' : '≡ Table'}
            </button>
          ))}
        </div>
      </div>

      {view === 'graph' ? (
        <AutomataGraph
          key={active}
          automaton={current.data}
          height={420}
        />
      ) : (
        <AutomataTable automaton={current.data} />
      )}
    </div>
  )
}
