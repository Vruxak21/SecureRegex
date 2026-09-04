import type { Automaton } from '../types'

function AutomataTable({ automaton, title }: { automaton: Automaton; title: string }) {
  return (
    <div className="space-y-4">
      {/* Summary row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: 'States', value: automaton.states.length },
          { label: 'Alphabet', value: automaton.alphabet.join(', ') || '∅' },
          { label: 'Start', value: `q${automaton.start}` },
          { label: 'Accepting', value: automaton.accepting.map(s => `q${s}`).join(', ') || '∅' },
        ].map(({ label, value }) => (
          <div key={label} className="bg-white/3 rounded-lg p-3 border border-white/8">
            <p className="text-xs text-white/30 mb-1">{label}</p>
            <p className="font-mono text-white/80 text-sm truncate">{value}</p>
          </div>
        ))}
      </div>

      {/* Transition table */}
      <div>
        <p className="text-xs text-white/30 uppercase tracking-wider mb-2">Transitions ({automaton.transitions.length})</p>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-white/10 text-left">
                <th className="py-2 px-3 text-white/40 font-medium">From</th>
                <th className="py-2 px-3 text-white/40 font-medium">Symbol</th>
                <th className="py-2 px-3 text-white/40 font-medium">To</th>
              </tr>
            </thead>
            <tbody>
              {automaton.transitions.map((t, i) => (
                <tr key={i} className="border-b border-white/5 hover:bg-white/3 transition-colors">
                  <td className="py-1.5 px-3 font-mono text-cyan-300">
                    {automaton.accepting.includes(t.from) ? '★ ' : ''}q{t.from}
                  </td>
                  <td className="py-1.5 px-3 font-mono text-amber-300">
                    {t.symbol === 'ε' ? <span className="text-purple-300">ε</span> : t.symbol}
                  </td>
                  <td className="py-1.5 px-3 font-mono text-cyan-300">
                    {automaton.accepting.includes(t.to) ? '★ ' : ''}q{t.to}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="text-[10px] text-white/20 mt-2">★ = accepting state</p>
      </div>

      {/* State list */}
      <div>
        <p className="text-xs text-white/30 uppercase tracking-wider mb-2">All States</p>
        <div className="flex flex-wrap gap-2">
          {automaton.states.map(s => (
            <span
              key={s}
              className={`px-2 py-1 rounded text-xs font-mono border ${
                s === automaton.start
                  ? 'bg-brand-500/20 text-brand-300 border-brand-500/40'
                  : automaton.accepting.includes(s)
                  ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
                  : 'bg-white/5 text-white/50 border-white/10'
              }`}
            >
              {s === automaton.start ? '→ ' : ''}
              q{s}
              {automaton.accepting.includes(s) ? ' ★' : ''}
            </span>
          ))}
        </div>
        <div className="flex gap-4 mt-2">
          <span className="text-[10px] text-white/20">→ start</span>
          <span className="text-[10px] text-emerald-400/40">★ accepting</span>
          <span className="text-[10px] text-brand-300/40">→★ start+accepting</span>
        </div>
      </div>
    </div>
  )
}

export default function AutomataTab({
  nfa, dfa, minimized_dfa
}: {
  nfa: Automaton
  dfa: Automaton
  minimized_dfa: Automaton
}) {
  const [active, setActive] = useState<'nfa' | 'dfa' | 'min'>('nfa')
  const tabs = [
    { id: 'nfa' as const, label: 'NFA', data: nfa },
    { id: 'dfa' as const, label: 'DFA', data: dfa },
    { id: 'min' as const, label: 'Min DFA', data: minimized_dfa },
  ]
  const current = tabs.find(t => t.id === active)!

  return (
    <div className="space-y-4">
      <div className="flex gap-2 border-b border-white/10 pb-3">
        {tabs.map(t => (
          <button
            key={t.id}
            onClick={() => setActive(t.id)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
              active === t.id
                ? 'bg-brand-600 text-white'
                : 'text-white/40 hover:text-white/70'
            }`}
          >
            {t.label}
            <span className="ml-1.5 text-[10px] opacity-60">{t.data.states.length}q</span>
          </button>
        ))}
      </div>
      <AutomataTable automaton={current.data} title={current.label} />
    </div>
  )
}

import { useState } from 'react'
