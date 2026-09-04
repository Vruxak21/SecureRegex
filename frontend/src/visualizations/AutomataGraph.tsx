/**
 * AutomataGraph.tsx
 *
 * Main React Flow wrapper. Renders an Automaton as an interactive graph:
 *  - Zoom / pan (built into React Flow)
 *  - Click a node  → shows details in a floating inspector panel
 *  - highlightedStates prop → used by traversal view to colour the path
 *
 * @xyflow/react v12 API is used throughout.
 */
import { useCallback, useMemo, useState } from 'react'
import {
  ReactFlow,
  Controls,
  Background,
  BackgroundVariant,
  useNodesState,
  useEdgesState,
  type NodeMouseHandler,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'

import type { Automaton } from '../types'
import { automataToFlow, type NodeData } from './automataToFlow'
import AutomataStateNode from './AutomataStateNode'

const nodeTypes = { automataState: AutomataStateNode }

interface Props {
  automaton: Automaton
  /** Set of state IDs to highlight (traversal path). */
  highlightedStates?: number[]
  /** Height of the canvas in px. */
  height?: number
}

interface InspectorState {
  kind: 'state'
  id: number
  isStart: boolean
  isAccepting: boolean
  outgoing: { symbol: string; to: number }[]
  incoming: { symbol: string; from: number }[]
}

export default function AutomataGraph({
  automaton,
  highlightedStates = [],
  height = 420,
}: Props) {
  const { nodes: initNodes, edges: initEdges } = useMemo(
    () => automataToFlow(automaton, highlightedStates),
    [automaton, highlightedStates],
  )

  const [nodes, , onNodesChange] = useNodesState(initNodes)
  const [edges, , onEdgesChange] = useEdgesState(initEdges)
  const [inspector, setInspector] = useState<InspectorState | null>(null)

  const onNodeClick: NodeMouseHandler = useCallback(
    (_, node) => {
      const stateId = (node.data as NodeData).stateId
      const outgoing = automaton.transitions
        .filter(t => t.from === stateId)
        .map(t => ({ symbol: t.symbol, to: t.to }))
      const incoming = automaton.transitions
        .filter(t => t.to === stateId)
        .map(t => ({ symbol: t.symbol, from: t.from }))
      setInspector({
        kind: 'state',
        id: stateId,
        isStart: stateId === automaton.start,
        isAccepting: automaton.accepting.includes(stateId),
        outgoing,
        incoming,
      })
    },
    [automaton],
  )

  const onPaneClick = useCallback(() => setInspector(null), [])

  return (
    <div className="relative w-full rounded-xl overflow-hidden border border-white/10"
         style={{ height }}
         data-testid="automata-graph">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={onNodeClick}
        onPaneClick={onPaneClick}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.35 }}
        minZoom={0.3}
        maxZoom={3}
        proOptions={{ hideAttribution: true }}
        style={{ background: 'transparent' }}
      >
        <Background
          variant={BackgroundVariant.Dots}
          gap={20}
          size={1}
          color="#ffffff0a"
        />
        <Controls
          showInteractive={false}
          style={{
            background: 'rgba(255,255,255,0.05)',
            border: '1px solid rgba(255,255,255,0.1)',
            borderRadius: 8,
          }}
        />
      </ReactFlow>

      {/* ── Inspector panel ── */}
      {inspector && (
        <div
          className="absolute top-3 right-3 bg-surface-800/95 backdrop-blur border border-white/10
                     rounded-xl p-4 w-56 text-xs space-y-2 shadow-xl animate-fade-in"
          data-testid="state-inspector"
        >
          <div className="flex items-center justify-between">
            <span className="font-mono font-bold text-white text-sm">
              q{inspector.id}
            </span>
            <button
              onClick={() => setInspector(null)}
              className="text-white/30 hover:text-white/70 transition-colors text-base leading-none"
            >
              ×
            </button>
          </div>

          <div className="flex flex-wrap gap-1">
            {inspector.isStart && (
              <span className="px-1.5 py-0.5 rounded bg-brand-500/20 text-brand-300 border border-brand-500/30">
                start
              </span>
            )}
            {inspector.isAccepting && (
              <span className="px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                accepting
              </span>
            )}
            {!inspector.isStart && !inspector.isAccepting && (
              <span className="text-white/30">normal state</span>
            )}
          </div>

          {inspector.outgoing.length > 0 && (
            <div>
              <p className="text-white/30 uppercase tracking-wider mb-1">Outgoing</p>
              {inspector.outgoing.map((t, i) => (
                <p key={i} className="font-mono text-white/60">
                  <span className="text-amber-400">{t.symbol}</span>
                  {' → '}
                  <span className="text-cyan-400">q{t.to}</span>
                </p>
              ))}
            </div>
          )}

          {inspector.incoming.length > 0 && (
            <div>
              <p className="text-white/30 uppercase tracking-wider mb-1">Incoming</p>
              {inspector.incoming.map((t, i) => (
                <p key={i} className="font-mono text-white/60">
                  <span className="text-cyan-400">q{t.from}</span>
                  {' '}
                  <span className="text-amber-400">{t.symbol}</span>
                </p>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Legend */}
      <div className="absolute bottom-2 left-3 flex items-center gap-3 text-[10px] text-white/25 select-none">
        <span>→ start</span>
        <span className="text-emerald-400/50">● accepting (double ring)</span>
        <span className="text-indigo-400/50">● highlighted</span>
      </div>
    </div>
  )
}
