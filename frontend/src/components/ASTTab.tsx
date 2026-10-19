import type { ASTNode } from '../types'

function ASTTree({ node, depth = 0 }: { node: ASTNode; depth?: number }) {
  const { type, ...rest } = node
  const indent = depth * 20

  return (
    <div style={{ marginLeft: indent }} className="my-1">
      <div className="flex items-center gap-2">
        <span className="token-badge">
          {String(type)}
        </span>
        {/* Inline leaf values */}
        {typeof rest.char === 'string' && (
          <span className="mono subtle">'{rest.char as string}'</span>
        )}
        {typeof rest.negate === 'boolean' && (
          <span className="subtle">{rest.negate ? 'negated' : ''}</span>
        )}
        {Array.isArray(rest.ranges) && (
          <span className="subtle mono">
            [{(rest.ranges as Array<{ start: string; end: string }>)
              .map(r => r.start === r.end ? r.start : `${r.start}-${r.end}`)
              .join(', ')}]
          </span>
        )}
      </div>
      {/* Recurse into child / left / right */}
      {rest.child && typeof rest.child === 'object' && (
        <div className="border-l border-white/10 ml-2 pl-2">
          <ASTTree node={rest.child as ASTNode} depth={depth + 1} />
        </div>
      )}
      {rest.left && typeof rest.left === 'object' && (
        <div className="border-l border-[#dbe3df] ml-2 pl-2">
          <span className="subtle mono">left</span>
          <ASTTree node={rest.left as ASTNode} depth={depth + 1} />
        </div>
      )}
      {rest.right && typeof rest.right === 'object' && (
        <div className="border-l border-[#dbe3df] ml-2 pl-2">
          <span className="subtle mono">right</span>
          <ASTTree node={rest.right as ASTNode} depth={depth + 1} />
        </div>
      )}
    </div>
  )
}

export default function ASTTab({ ast }: { ast: ASTNode }) {
  return (
    <div className="overflow-auto max-h-[480px] pr-2">
      <p className="subtle" style={{ marginBottom: 18 }}>
        The parser turns the token stream into a tree that records grouping, repetition, and alternatives.
      </p>
      <ASTTree node={ast} />
    </div>
  )
}
