import type { Token } from '../types'
export default function TokensTab({ tokens }: { tokens: Token[] }) {
  return <div><p className="subtle">The lexer reads the pattern one symbol at a time and assigns each symbol a role.</p>
    <div style={{ overflowX: 'auto' }}><table className="light-table"><thead><tr><th>#</th><th>Token</th><th>Value</th><th>Column</th></tr></thead><tbody>
      {tokens.map((token, index) => <tr key={index}><td className="mono">{index + 1}</td><td><span className="token-badge">{token.type}</span></td><td className="mono">{token.value || 'ε'}</td><td className="mono">{token.column}</td></tr>)}
    </tbody></table></div>
  </div>
}
