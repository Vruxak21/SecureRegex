import { BaseEdge } from '@xyflow/react'
import type { Edge, EdgeProps } from '@xyflow/react'
import type { EdgeData } from './automataToFlow'

type SelfLoopEdgeProps = EdgeProps<Edge<EdgeData>>

/**
 * Draw a self-loop above the state instead of underneath it.
 *
 * React Flow's built-in self-connecting edge uses the node handles as the
 * loop anchor. Our state handles are invisible and sit inside the node, so
 * the default path can be covered by the node itself.
 */
export default function SelfLoopEdge({
  sourceX,
  sourceY,
  targetX,
  targetY,
  markerEnd,
  label,
  labelStyle,
  labelBgStyle,
  style,
}: SelfLoopEdgeProps) {
  const path = [
    `M ${sourceX} ${sourceY}`,
    `C ${sourceX + 46} ${sourceY - 82},`,
    `${targetX - 46} ${targetY - 82},`,
    `${targetX} ${targetY}`,
  ].join(' ')

  return (
    <BaseEdge
      path={path}
      labelX={(sourceX + targetX) / 2}
      labelY={sourceY - 68}
      label={label}
      labelStyle={labelStyle}
      labelBgStyle={labelBgStyle}
      markerEnd={markerEnd}
      style={style}
    />
  )
}
