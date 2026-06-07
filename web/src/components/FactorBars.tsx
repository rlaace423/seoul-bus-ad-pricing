import type { Factor } from '../lib/grid'
import { factorLabel } from '../lib/labels'
import { signedPct } from '../lib/format'

export default function FactorBars({ factors }: { factors: Factor[] }) {
  const max = Math.max(...factors.map((f) => Math.abs(f.pct)), 1)
  return (
    <div className="factors">
      {factors.map((f) => {
        const up = f.pct >= 0
        return (
          <div className="factor" key={f.name}>
            <div className="factor__head">
              <span className="factor__name">{factorLabel(f.name)}</span>
              <span className={`factor__pct ${up ? 'up' : 'down'}`}>
                {up ? '▲' : '▼'} {signedPct(f.pct)}
              </span>
            </div>
            <div className="factor__track">
              <div
                className={`factor__bar ${up ? 'up' : 'down'}`}
                style={{ width: `${(Math.abs(f.pct) / max) * 100}%` }}
              />
            </div>
          </div>
        )
      })}
    </div>
  )
}
