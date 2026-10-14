/**
 * Phase 10 — Visualization tests.
 *
 * React Flow internally uses ResizeObserver and dynamic SVG which are not
 * available in jsdom. Strategy: mock @xyflow/react so the hook/component
 * contract is tested without needing a real DOM renderer, and test the
 * pure conversion utility (automataToFlow) directly — it has no DOM deps.
 *
 * Test groups:
 *   A. automataToFlow utility — pure function, no React
 *   B. AutomataGraph render  — mocked RF, checks node/edge counts + aria
 *   C. AutomataStateNode     — custom node rendering (accepting, start, highlighted)
 *   D. AutomataTab           — graph/table toggle UI
 *   E. TestRegexTab          — traversal path highlighting
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'

// ── Mock @xyflow/react ────────────────────────────────────────────────────────
// jsdom has no ResizeObserver; mock the whole library before any import.
vi.mock('@xyflow/react', () => {
  const React = require('react')
  return {
    ReactFlow: ({ nodes, edges, onNodeClick }: {
      nodes: unknown[]; edges: unknown[];
      onNodeClick?: (e: unknown, node: unknown) => void
    }) =>
      React.createElement('div', { 'data-testid': 'react-flow', 'data-nodes': nodes.length, 'data-edges': edges.length },
        nodes.map((n: any) =>
          React.createElement('div', {
            key: n.id,
            'data-testid': `node-${n.id}`,
            'data-accepting': String(n.data?.isAccepting ?? false),
            'data-start':     String(n.data?.isStart ?? false),
            'data-highlighted': String(n.data?.isHighlighted ?? false),
            onClick: () => onNodeClick?.({} as any, n as any),
          }, n.data?.label)
        ),
      ),
    Controls:   () => null,
    Background: () => null,
    BackgroundVariant: { Dots: 'dots' },
    Handle:     () => null,
    Position:   { Left: 'left', Right: 'right' },
    useNodesState: (init: unknown[]) => [init, () => {}, () => {}],
    useEdgesState: (init: unknown[]) => [init, () => {}, () => {}],
  }
})

// ── Fixtures ──────────────────────────────────────────────────────────────────

const DFA_AORB_ABB = {
  states: [0, 1, 2, 3, 4],
  alphabet: ['a', 'b'],
  transitions: [
    { from: 0, symbol: 'a', to: 1 },
    { from: 0, symbol: 'b', to: 2 },
    { from: 1, symbol: 'a', to: 1 },
    { from: 1, symbol: 'b', to: 3 },
    { from: 2, symbol: 'a', to: 1 },
    { from: 2, symbol: 'b', to: 2 },
    { from: 3, symbol: 'a', to: 1 },
    { from: 3, symbol: 'b', to: 4 },
    { from: 4, symbol: 'a', to: 1 },
    { from: 4, symbol: 'b', to: 2 },
  ],
  start: 0,
  accepting: [4],
}

const MIN_DFA_AORB_ABB = {
  states: [0, 1, 2, 3],
  alphabet: ['a', 'b'],
  transitions: [
    { from: 0, symbol: 'a', to: 1 },
    { from: 0, symbol: 'b', to: 0 },
    { from: 1, symbol: 'a', to: 1 },
    { from: 1, symbol: 'b', to: 2 },
    { from: 2, symbol: 'a', to: 1 },
    { from: 2, symbol: 'b', to: 3 },
    { from: 3, symbol: 'a', to: 1 },
    { from: 3, symbol: 'b', to: 0 },
  ],
  start: 0,
  accepting: [3],
}

const NFA_AORB_ABB = {
  states: Array.from({ length: 14 }, (_, i) => i),
  alphabet: ['a', 'b'],
  transitions: [
    { from: 0, symbol: 'a',  to: 1  },
    { from: 1, symbol: 'ε',  to: 5  },
    { from: 2, symbol: 'b',  to: 3  },
    { from: 3, symbol: 'ε',  to: 5  },
    { from: 4, symbol: 'ε',  to: 0  },
    { from: 4, symbol: 'ε',  to: 2  },
    { from: 5, symbol: 'ε',  to: 4  },
    { from: 5, symbol: 'ε',  to: 7  },
    { from: 6, symbol: 'ε',  to: 4  },
    { from: 6, symbol: 'ε',  to: 7  },
    { from: 7, symbol: 'ε',  to: 8  },
    { from: 8, symbol: 'a',  to: 9  },
    { from: 9, symbol: 'ε',  to: 10 },
    { from: 10, symbol: 'b', to: 11 },
    { from: 11, symbol: 'ε', to: 12 },
    { from: 12, symbol: 'b', to: 13 },
  ],
  start: 6,
  accepting: [13],
}

// ── A. automataToFlow utility ─────────────────────────────────────────────────

import { automataToFlow } from '../src/visualizations/automataToFlow'

describe('automataToFlow — pure conversion', () => {

  describe('DFA (a|b)*abb — 5 states, 10 transitions', () => {
    const { nodes, edges } = automataToFlow(DFA_AORB_ABB)

    it('produces 5 nodes for 5 DFA states', () => {
      expect(nodes).toHaveLength(5)
    })

    it('every node has a unique id matching its state number', () => {
      const ids = nodes.map(n => n.id)
      expect(new Set(ids).size).toBe(5)
      expect(ids).toContain('0')
      expect(ids).toContain('4')
    })

    it('start state node has isStart=true', () => {
      const startNode = nodes.find(n => n.data.stateId === 0)
      expect(startNode?.data.isStart).toBe(true)
    })

    it('non-start nodes have isStart=false', () => {
      nodes.filter(n => n.data.stateId !== 0)
        .forEach(n => expect(n.data.isStart).toBe(false))
    })

    it('accepting state node has isAccepting=true', () => {
      const acceptNode = nodes.find(n => n.data.stateId === 4)
      expect(acceptNode?.data.isAccepting).toBe(true)
    })

    it('non-accepting nodes have isAccepting=false', () => {
      nodes.filter(n => !DFA_AORB_ABB.accepting.includes(n.data.stateId))
        .forEach(n => expect(n.data.isAccepting).toBe(false))
    })

    it('parallel edges are merged — 10 transitions → ≤10 edges (some may merge)', () => {
      // 10 transitions, all distinct pairs, so 10 edges
      expect(edges.length).toBe(10)
    })

    it('edge labels contain the input symbol', () => {
      const edgeLabels = edges.map(e => String(e.label))
      expect(edgeLabels.some(l => l.includes('a'))).toBe(true)
      expect(edgeLabels.some(l => l.includes('b'))).toBe(true)
    })

    it('node type is automataState', () => {
      nodes.forEach(n => expect(n.type).toBe('automataState'))
    })

    it('all nodes have position with x and y', () => {
      nodes.forEach(n => {
        expect(typeof n.position.x).toBe('number')
        expect(typeof n.position.y).toBe('number')
      })
    })
  })

  describe('Minimized DFA — 4 states', () => {
    const { nodes, edges } = automataToFlow(MIN_DFA_AORB_ABB)

    it('produces 4 nodes', () => {
      expect(nodes).toHaveLength(4)
    })

    it('accepting state q3 is marked isAccepting', () => {
      const n = nodes.find(n => n.data.stateId === 3)
      expect(n?.data.isAccepting).toBe(true)
    })

    it('self-loop on q0 (b→q0) creates an edge from 0 to 0', () => {
      const selfLoop = edges.find(e => e.source === '0' && e.target === '0')
      expect(selfLoop).toBeDefined()
      expect(selfLoop?.type).toBe('selfLoop')
    })

    it('produces 8 edges for 8 transitions', () => {
      expect(edges).toHaveLength(8)
    })
  })

  describe('NFA — 14 states, ε-transitions', () => {
    const { nodes, edges } = automataToFlow(NFA_AORB_ABB)

    it('produces 14 nodes', () => {
      expect(nodes).toHaveLength(14)
    })

    it('ε edges have the epsilon symbol in their label', () => {
      const epsEdge = edges.find(e => String(e.label).includes('ε'))
      expect(epsEdge).toBeDefined()
    })

    it('accepting state q13 is marked isAccepting', () => {
      const n = nodes.find(n => n.data.stateId === 13)
      expect(n?.data.isAccepting).toBe(true)
    })

    it('start state is q6', () => {
      const n = nodes.find(n => n.data.stateId === 6)
      expect(n?.data.isStart).toBe(true)
    })
  })

  describe('Traversal highlighting', () => {
    it('highlighted states get isHighlighted=true', () => {
      const { nodes } = automataToFlow(DFA_AORB_ABB, [0, 1, 3])
      const highlighted = nodes.filter(n => n.data.isHighlighted)
      expect(highlighted.map(n => n.data.stateId).sort()).toEqual([0, 1, 3])
    })

    it('non-highlighted states have isHighlighted=false or undefined', () => {
      const { nodes } = automataToFlow(DFA_AORB_ABB, [0])
      nodes.filter(n => n.data.stateId !== 0)
        .forEach(n => expect(n.data.isHighlighted).toBeFalsy())
    })

    it('empty highlightedStates means no node is highlighted', () => {
      const { nodes } = automataToFlow(DFA_AORB_ABB, [])
      nodes.forEach(n => expect(n.data.isHighlighted).toBeFalsy())
    })
  })
})

// ── B. AutomataGraph render ───────────────────────────────────────────────────

import AutomataGraph from '../src/visualizations/AutomataGraph'

describe('AutomataGraph component', () => {
  it('renders the react-flow container', () => {
    render(<AutomataGraph automaton={DFA_AORB_ABB} />)
    expect(screen.getByTestId('automata-graph')).toBeInTheDocument()
  })

  it('renders 5 node elements for DFA with 5 states', () => {
    render(<AutomataGraph automaton={DFA_AORB_ABB} />)
    const rf = screen.getByTestId('react-flow')
    expect(Number(rf.getAttribute('data-nodes'))).toBe(5)
  })

  it('renders 10 edge elements for DFA with 10 transitions', () => {
    render(<AutomataGraph automaton={DFA_AORB_ABB} />)
    const rf = screen.getByTestId('react-flow')
    expect(Number(rf.getAttribute('data-edges'))).toBe(10)
  })

  it('renders 14 node elements for NFA with 14 states', () => {
    render(<AutomataGraph automaton={NFA_AORB_ABB} />)
    const rf = screen.getByTestId('react-flow')
    expect(Number(rf.getAttribute('data-nodes'))).toBe(14)
  })

  it('accepting state node has data-accepting=true', () => {
    render(<AutomataGraph automaton={DFA_AORB_ABB} />)
    const acceptNode = screen.getByTestId('node-4')
    expect(acceptNode.getAttribute('data-accepting')).toBe('true')
  })

  it('non-accepting states have data-accepting=false', () => {
    render(<AutomataGraph automaton={DFA_AORB_ABB} />)
    ;[0,1,2,3].forEach(id => {
      const n = screen.getByTestId(`node-${id}`)
      expect(n.getAttribute('data-accepting')).toBe('false')
    })
  })

  it('start state node has data-start=true', () => {
    render(<AutomataGraph automaton={DFA_AORB_ABB} />)
    const startNode = screen.getByTestId('node-0')
    expect(startNode.getAttribute('data-start')).toBe('true')
  })

  it('highlighted states are marked in the rendered nodes', () => {
    render(<AutomataGraph automaton={DFA_AORB_ABB} highlightedStates={[0, 1]} />)
    expect(screen.getByTestId('node-0').getAttribute('data-highlighted')).toBe('true')
    expect(screen.getByTestId('node-1').getAttribute('data-highlighted')).toBe('true')
    expect(screen.getByTestId('node-2').getAttribute('data-highlighted')).toBe('false')
  })

  it('clicking a node shows the inspector panel', () => {
    render(<AutomataGraph automaton={DFA_AORB_ABB} />)
    fireEvent.click(screen.getByTestId('node-0'))
    expect(screen.getByTestId('state-inspector')).toBeInTheDocument()
  })

  it('inspector shows state id', () => {
    render(<AutomataGraph automaton={DFA_AORB_ABB} />)
    fireEvent.click(screen.getByTestId('node-0'))
    expect(screen.getByTestId('state-inspector').textContent).toContain('q0')
  })

  it('min DFA: renders 4 nodes', () => {
    render(<AutomataGraph automaton={MIN_DFA_AORB_ABB} />)
    expect(Number(screen.getByTestId('react-flow').getAttribute('data-nodes'))).toBe(4)
  })
})

// ── C. AutomataStateNode ──────────────────────────────────────────────────────

import AutomataStateNode from '../src/visualizations/AutomataStateNode'

const makeProps = (overrides: Partial<{
  isStart: boolean; isAccepting: boolean; isHighlighted: boolean
}> = {}) => ({
  id: '0',
  type: 'automataState',
  selected: false,
  zIndex: 0,
  isConnectable: true,
  xPos: 0,
  yPos: 0,
  dragging: false,
  data: {
    label: 'q0',
    stateId: 0,
    isStart: false,
    isAccepting: false,
    isHighlighted: false,
    ...overrides,
  },
  positionAbsoluteX: 0,
  positionAbsoluteY: 0,
})

describe('AutomataStateNode', () => {
  it('renders the state label', () => {
    render(<AutomataStateNode {...makeProps()} />)
    expect(screen.getByText('q0')).toBeInTheDocument()
  })

  it('accepting state renders inner double-border div', () => {
    const { container } = render(<AutomataStateNode {...makeProps({ isAccepting: true })} />)
    // The double-border is an absolute inset div with rounded-full
    const inner = container.querySelector('.absolute.inset-1.rounded-full')
    expect(inner).toBeInTheDocument()
  })

  it('non-accepting state has no double-border div', () => {
    const { container } = render(<AutomataStateNode {...makeProps({ isAccepting: false })} />)
    const inner = container.querySelector('.absolute.inset-1.rounded-full')
    expect(inner).not.toBeInTheDocument()
  })

  it('start state renders arrow indicator', () => {
    render(<AutomataStateNode {...makeProps({ isStart: true })} />)
    expect(screen.getByText('→')).toBeInTheDocument()
  })

  it('non-start state has no arrow indicator', () => {
    render(<AutomataStateNode {...makeProps({ isStart: false })} />)
    expect(screen.queryByText('→')).not.toBeInTheDocument()
  })
})

// ── D. AutomataTab ────────────────────────────────────────────────────────────

import AutomataTab from '../src/components/AutomataTab'

describe('AutomataTab — graph/table toggle', () => {
  const props = { nfa: NFA_AORB_ABB, dfa: DFA_AORB_ABB, minimized_dfa: MIN_DFA_AORB_ABB }

  it('renders graph view by default', () => {
    render(<AutomataTab {...props} />)
    expect(screen.getByTestId('automata-graph')).toBeInTheDocument()
  })

  it('shows NFA, DFA, Min DFA sub-tab buttons', () => {
    render(<AutomataTab {...props} />)
    expect(screen.getByText(/NFA/)).toBeInTheDocument()
    // "DFA" appears in both "DFA" and "Min DFA" buttons — use getAllByText
    expect(screen.getAllByText(/DFA/).length).toBeGreaterThanOrEqual(2)
    expect(screen.getByText(/Min DFA/)).toBeInTheDocument()
  })

  it('switching to Table view hides the graph', () => {
    render(<AutomataTab {...props} />)
    fireEvent.click(screen.getByText('≡ Table'))
    expect(screen.queryByTestId('automata-graph')).not.toBeInTheDocument()
  })

  it('switching back to Graph view shows it again', () => {
    render(<AutomataTab {...props} />)
    fireEvent.click(screen.getByText('≡ Table'))
    fireEvent.click(screen.getByText('⬡ Graph'))
    expect(screen.getByTestId('automata-graph')).toBeInTheDocument()
  })

  it('DFA sub-tab shows DFA graph (5 nodes)', () => {
    render(<AutomataTab {...props} />)
    fireEvent.click(screen.getByText(/^DFA/))
    const rf = screen.getByTestId('react-flow')
    expect(Number(rf.getAttribute('data-nodes'))).toBe(5)
  })

  it('Min DFA sub-tab shows 4-node graph', () => {
    render(<AutomataTab {...props} />)
    fireEvent.click(screen.getByText(/Min DFA/))
    const rf = screen.getByTestId('react-flow')
    expect(Number(rf.getAttribute('data-nodes'))).toBe(4)
  })

  it('updates the mounted graph when switching between automata', () => {
    render(<AutomataTab {...props} />)

    expect(Number(screen.getByTestId('react-flow').getAttribute('data-nodes'))).toBe(14)

    fireEvent.click(screen.getByText(/^DFA/))
    expect(Number(screen.getByTestId('react-flow').getAttribute('data-nodes'))).toBe(5)

    fireEvent.click(screen.getByText(/Min DFA/))
    expect(Number(screen.getByTestId('react-flow').getAttribute('data-nodes'))).toBe(4)
  })
})

// ── E. Traversal highlighting ─────────────────────────────────────────────────

describe('Traversal highlighting via automataToFlow', () => {
  // "abb" on MIN_DFA path = [0, 1, 2, 3]
  const traversalPath = [0, 1, 2, 3]

  it('path step 0 highlights only q0', () => {
    const { nodes } = automataToFlow(MIN_DFA_AORB_ABB, traversalPath.slice(0, 1))
    expect(nodes.find(n => n.data.stateId === 0)?.data.isHighlighted).toBe(true)
    expect(nodes.find(n => n.data.stateId === 1)?.data.isHighlighted).toBe(false)
  })

  it('path step 2 highlights q0, q1, q2', () => {
    const { nodes } = automataToFlow(MIN_DFA_AORB_ABB, traversalPath.slice(0, 3))
    ;[0, 1, 2].forEach(id =>
      expect(nodes.find(n => n.data.stateId === id)?.data.isHighlighted).toBe(true)
    )
    expect(nodes.find(n => n.data.stateId === 3)?.data.isHighlighted).toBe(false)
  })

  it('full path highlights all 4 states', () => {
    const { nodes } = automataToFlow(MIN_DFA_AORB_ABB, traversalPath)
    ;[0, 1, 2, 3].forEach(id =>
      expect(nodes.find(n => n.data.stateId === id)?.data.isHighlighted).toBe(true)
    )
  })

  it('final state q3 is accepting AND highlighted when path is complete', () => {
    const { nodes } = automataToFlow(MIN_DFA_AORB_ABB, traversalPath)
    const final = nodes.find(n => n.data.stateId === 3)!
    expect(final.data.isHighlighted).toBe(true)
    expect(final.data.isAccepting).toBe(true)
  })

  it('rendering with highlighted states marks them in DOM', () => {
    render(<AutomataGraph automaton={MIN_DFA_AORB_ABB} highlightedStates={[0, 1, 2, 3]} />)
    ;[0, 1, 2, 3].forEach(id => {
      expect(screen.getByTestId(`node-${id}`).getAttribute('data-highlighted')).toBe('true')
    })
  })
})
