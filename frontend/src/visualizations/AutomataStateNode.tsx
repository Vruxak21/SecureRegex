/**
 * AutomataStateNode.tsx
 *
 * Custom React Flow node type for an automaton state.
 *
 * Visual rules:
 *  - Accepting state: double-ring outer border (box-shadow trick)
 *  - Start state: filled brand-blue background
 *  - Highlighted (traversal): bright indigo glow
 *  - Normal: subtle dark surface
 *
 * Clicking a node fires onStateClick (passed via RF nodeTypes context).
 */
import { memo } from 'react'
import { Handle, Position } from '@xyflow/react'
import type { NodeProps } from '@xyflow/react'
import type { NodeData } from './automataToFlow'

function AutomataStateNode({ data, selected }: NodeProps<NodeData>) {
  const { label, isStart, isAccepting, isHighlighted } = data

  let base = 'bg-surface-700 border-white/20 text-white/70'
  let ring = ''
  let glow = ''

  if (isHighlighted) {
    base = 'bg-indigo-900/80 border-indigo-400 text-indigo-200'
    glow = 'shadow-[0_0_16px_4px_rgba(99,102,241,0.5)]'
  } else if (isStart && isAccepting) {
    base = 'bg-brand-900/80 border-brand-400 text-brand-200'
    ring = 'ring-2 ring-offset-2 ring-offset-surface-800 ring-emerald-400'
  } else if (isStart) {
    base = 'bg-brand-900/60 border-brand-400 text-brand-200'
  } else if (isAccepting) {
    base = 'bg-emerald-900/50 border-emerald-400 text-emerald-200'
    ring = 'ring-2 ring-offset-2 ring-offset-surface-800 ring-emerald-500/60'
  }

  if (selected) {
    glow = `${glow} shadow-[0_0_12px_2px_rgba(139,92,246,0.6)]`
  }

  return (
    <div
      className={`
        relative flex items-center justify-center
        w-14 h-14 rounded-full
        border-2 font-mono text-xs font-bold
        transition-all duration-200 cursor-pointer
        ${base} ${ring} ${glow}
      `}
    >
      {/* Arrow indicator for start state */}
      {isStart && (
        <span className="absolute -left-6 text-brand-400 text-base font-bold select-none">→</span>
      )}

      {label}

      {/* Double-border for accepting state */}
      {isAccepting && (
        <div className="absolute inset-1 rounded-full border border-current opacity-40 pointer-events-none" />
      )}

      {/* RF connection handles (invisible) */}
      <Handle type="target" position={Position.Left}  style={{ opacity: 0, width: 0, height: 0 }} />
      <Handle type="source" position={Position.Right} style={{ opacity: 0, width: 0, height: 0 }} />
    </div>
  )
}

export default memo(AutomataStateNode)
