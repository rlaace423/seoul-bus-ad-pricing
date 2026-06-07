import { PRICE_STOPS } from '../lib/grid'
import { VALUE_STOPS } from '../lib/stops'
import { manWon } from '../lib/format'

export type LegendMode = 'price' | 'value' | 'verdict' | 'candval'

export default function Legend({ mode }: { mode: LegendMode }) {
  if (mode === 'verdict') {
    return (
      <div className="legend">
        <div className="legend__title">현재 광고판 — 예측 대비 가격</div>
        <div className="legend__cats">
          <span><i style={{ background: '#3fb96b' }} />저평가</span>
          <span><i style={{ background: '#7d7d8c' }} />적정</span>
          <span><i style={{ background: '#ff6b5e' }} />고평가</span>
        </div>
        <div className="legend__note">원 크기 = 일 이용객 수</div>
      </div>
    )
  }
  if (mode === 'value') {
    const g = `linear-gradient(to right, ${VALUE_STOPS.map((s) => s[1]).join(',')})`
    return (
      <div className="legend">
        <div className="legend__title">정류장 가성비 (노출 대비 가격)</div>
        <div className="legend__bar" style={{ background: g }} />
        <div className="legend__ticks"><span>비쌈/한산</span><span>보통</span><span>싸고 붐빔</span></div>
        <div className="legend__note">원 크기 = 일 이용객 수</div>
      </div>
    )
  }
  // price / candval — both use the predicted-price ramp
  const g = `linear-gradient(to right, ${PRICE_STOPS.map((s) => s[1]).join(',')})`
  return (
    <div className="legend">
      <div className="legend__title">{mode === 'candval' ? '신설 시 예상 광고가' : '예상 광고가'} (원/면·월)</div>
      <div className="legend__bar" style={{ background: g }} />
      <div className="legend__ticks">
        <span>{manWon(PRICE_STOPS[0][0])}</span>
        <span>{manWon(PRICE_STOPS[Math.floor(PRICE_STOPS.length / 2)][0])}</span>
        <span>{manWon(PRICE_STOPS[PRICE_STOPS.length - 1][0])}+</span>
      </div>
      {mode === 'candval' && <div className="legend__note">원 크기 = 신설 가치</div>}
    </div>
  )
}
