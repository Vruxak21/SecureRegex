/**
 * automataToFlow.ts
 *
 * Converts the backend Automaton JSON into React Flow nodes + edges.
 *
 * Layout strategy: deterministic circular layout so tests always produce
 * stable node positions without needing a layout library (dagre etc.).
 * For graphs with > 1 state the start state is placed at the left,
 * remaining states evenly spaced around a circle of radius R.
 */

import type { Node, Edge } from '@xyflow/react'
import type { Automaton, AutomataTransition } from '../types'

export type NodeData = {
  label: string
  stateId: number
  isStart: boolean
  isAccepting: boolean
  isHighlighted?: boolean   // used in traversal view
}

export type EdgeData = {
  symbol: string
}

/** Circular layout: start at 9 o'clock, rest clockwise. */
function circularLayout(
  states: number[],
  startState: number,
  radius = 160,
  cx = 250,
  cy = 220,
): Record<number, { x: number; y: number }> {
  const positions: Record<number, { x: number; y: number }> = {}
  const others = states.filter(s => s !== startState)

  // Start state fixed at left-centre
  positions[startState] = { x: cx - radius, y: cy }

  if (others.length === 0) return positions

  // For a single other state, place it at the right
  if (others.length === 1) {
    positions[others[0]] = { x: cx + radius, y: cy }
    return positions
  }

  // Spread remaining states around a circle, starting from top
  others.forEach((s, i) => {
    const angle = (2 * Math.PI * i) / others.length - Math.PI / 2
    positions[s] = {
      x: cx + radius * Math.cos(angle),
      y: cy + radius * Math.sin(angle),
    }
  })
  return positions
}

/**
 * Merge parallel edges (same from/to) into a single edge with a
 * comma-separated label to avoid overlapping arrows.
 */
function mergeTransitions(
  transitions: AutomataTransition[],
): { from: number; to: number; symbols: string[] }[] {
  const map = new Map<string, string[]>()
  for (const t of transitions) {
    const key = `${t.from}→${t.to}`
    if (!map.has(key)) map.set(key, [])
    map.get(key)!.push(t.symbol)
  }
  return Array.from(map.entries()).map(([key, symbols]) => {
    const [from, to] = key.split('→').map(Number)
    return { from, to, symbols }
  })
}

/** Convert an Automaton to React Flow nodes + edges. */
export function automataToFlow(
  automaton: Automaton,
  highlightedStates: number[] = [],
): { nodes: Node<NodeData>[]; edges: Edge<EdgeData>[] } {
  const highlighted = new Set(highlightedStates)
  const pos = circularLayout(automaton.states, automaton.start)

  const nodes: Node<NodeData>[] = automaton.states.map(s => ({
    id: String(s),
    type: 'automataState',
    position: pos[s] ?? { x: 0, y: 0 },
    data: {
      label: `q${s}`,
      stateId: s,
      isStart: s === automaton.start,
      isAccepting: automaton.accepting.includes(s),
      isHighlighted: highlighted.has(s),
    },
  }))

  const merged = mergeTransitions(automaton.transitions)

  const edges: Edge<EdgeData>[] = merged.map(({ from, to, symbols }) => {
    const label = symbols.join(', ')
    const isSelfLoop = from === to
    const isHighlightedEdge = false // traversal highlighting is on nodes only
    return {
      id: `e${from}-${to}`,
      source: String(from),
      target: String(to),
      label,
      type: isSelfLoop ? 'selfConnecting' : 'default',
      animated: false,
      data: { symbol: label },
      style: {
        stroke: isHighlightedEdge ? '#6366f1' : '#ffffff30',
        strokeWidth: 1.5,
      },
      labelStyle: {
        fill: '#f59e0b',
        fontSize: 11,
        fontFamily: 'JetBrains Mono, monospace',
        fontWeight: 600,
      },
      labelBgStyle: {
        fill: '#1e1b2e',
        fillOpacity: 0.85,
      },
      markerEnd: {
        type: 'arrowclosed' as const,
        color: '#ffffff30',
        width: 14,
        height: 14,
      },
    }
  })

  return { nodes, edges }
}
