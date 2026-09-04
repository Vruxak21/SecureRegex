import type { Token } from '../types'

export default function TokensTab({ tokens }: { tokens: Token[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-white/10 text-left">
            <th className="py-2 px-3 text-white/40 font-medium text-xs uppercase tracking-wider w-12">#</th>
            <th className="py-2 px-3 text-white/40 font-medium text-xs uppercase tracking-wider">Type</th>
            <th className="py-2 px-3 text-white/40 font-medium text-xs uppercase tracking-wider">Value</th>
            <th className="py-2 px-3 text-white/40 font-medium text-xs uppercase tracking-wider w-24">Column</th>
          </tr>
        </thead>
        <tbody>
          {tokens.map((tok, i) => (
            <tr key={i} className="border-b border-white/5 hover:bg-white/3 transition-colors">
              <td className="py-2 px-3 text-white/30 font-mono text-xs">{i + 1}</td>
              <td className="py-2 px-3">
                <span className="px-2 py-0.5 rounded text-xs font-mono bg-brand-500/20 text-brand-300 border border-brand-500/30">
                  {tok.type}
                </span>
              </td>
              <td className="py-2 px-3 font-mono text-white/80 text-xs">
                {tok.value === '' ? <span className="text-white/20 italic">ε</span> : tok.value}
              </td>
              <td className="py-2 px-3 text-white/30 font-mono text-xs">{tok.column}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
