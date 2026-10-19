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

  let base = 'bg-white border-[#9fb4af] text-[#1c2a35]'
  let ring = ''
  let glow = ''

  if (isHighlighted) {
    base = 'bg-[#e3f2ef] border-[#087f79] text-[#075b59]'
    glow = 'shadow-[0_0_16px_4px_rgba(8,127,121,0.25)]'
  } else if (isStart && isAccepting) {
    base = 'bg-[#d8efeb] border-[#087f79] text-[#075b59]'
    ring = 'ring-2 ring-offset-2 ring-offset-white ring-[#c58b28]'
  } else if (isStart) {
    base = 'bg-[#e3f2ef] border-[#087f79] text-[#075b59]'
  } else if (isAccepting) {
    base = 'bg-[#edf7f4] border-[#27967d] text-[#075b59]'
    ring = 'ring-2 ring-offset-2 ring-offset-white ring-[#27967d]'
  }

  if (selected) {
    glow = `${glow} shadow-[0_0_12px_2px_rgba(8,127,121,0.3)]`
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
        <span className="absolute -left-6 text-[#087f79] text-base font-bold select-none">→</span>
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
