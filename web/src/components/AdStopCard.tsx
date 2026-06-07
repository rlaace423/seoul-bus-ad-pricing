import type { Stop } from '../lib/stops'
import type { Cell } from '../lib/grid'
import { manWon } from '../lib/format'
import FactorBars from './FactorBars'

function verdict(actual: number, lo: number, hi: number): { key: string; label: string } {
  if (actual < lo) return { key: 'under', label: '저평가 · 예측보다 저렴' }
  if (actual > hi) return { key: 'over', label: '고평가 · 예측보다 비쌈' }
  return { key: 'fair', label: '적정 범위' }
}

export default function AdStopCard({ stop, gridCell }: { stop: Stop; gridCell: Cell | null }) {
  const pred = gridCell?.price ?? stop.predValue ?? null
  return (
    <div className="panel-body">
      <div className="row-between">
        <span className="gu">{stop.name}</span>
        <span className="stop-check__tag">현재 광고판</span>
      </div>
      <div className="stop-gu">{stop.gu}</div>

      <div className="metrics">
        <div className="metric">
          <div className="metric__num">{manWon(stop.price)}원</div>
          <div className="metric__lbl">실제 광고가</div>
        </div>
        <div className="metric">
          <div className="metric__num">{pred != null ? `${manWon(pred)}원` : '—'}</div>
          <div className="metric__lbl">예측 적정가</div>
        </div>
      </div>

      {gridCell && (() => {
        const v = verdict(stop.price, gridCell.lo, gridCell.hi)
        const diff = (stop.price / gridCell.price - 1) * 100
        return (
          <div className={`verdict verdict--${v.key}`} style={{ marginBottom: 18 }}>
            <b>{v.label}</b>
            <span>예측가 대비 {diff >= 0 ? '+' : ''}{diff.toFixed(0)}% · 범위 {manWon(gridCell.lo)}~{manWon(gridCell.hi)}원</span>
          </div>
        )
      })()}

      {gridCell && (
        <>
          <div className="section-title">이 위치의 가격을 만든 요인</div>
          <p className="section-hint">도시 구조가 예측 광고가를 올린(▲) / 내린(▼) 정도</p>
          <FactorBars factors={gridCell.factors} />
        </>
      )}

      <p className="disclaimer">
        실제가는 덕플레이스 수집가(<b>추정 호가</b>), 예측 적정가는 인근 도시 구조 기반 모델값입니다. 단위 1면·월.
      </p>
    </div>
  )
}
