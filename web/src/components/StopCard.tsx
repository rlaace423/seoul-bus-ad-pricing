import { Users, Coins } from 'lucide-react'
import type { Stop } from '../lib/stops'
import type { Cell } from '../lib/grid'
import { manWon, won } from '../lib/format'
import FactorBars from './FactorBars'

function valueTier(vp: number | null): { label: string; cls: string } {
  if (vp == null) return { label: '이용객 데이터 없음', cls: 'na' }
  if (vp >= 80) return { label: '가성비 우수', cls: 'good' }
  if (vp >= 55) return { label: '가성비 양호', cls: 'ok' }
  if (vp >= 30) return { label: '가성비 보통', cls: 'mid' }
  return { label: '가성비 낮음', cls: 'low' }
}

export default function StopCard({ stop, gridCell }: { stop: Stop; gridCell: Cell | null }) {
  const tier = valueTier(stop.valuePct)
  const topPct = stop.valuePct != null ? Math.max(1, 100 - stop.valuePct) : null

  return (
    <div className="panel-body">
      <div className="row-between">
        <span className="gu">{stop.name}</span>
        <span className={`vtag vtag--${tier.cls}`}>{tier.label}</span>
      </div>
      <div className="stop-gu">{stop.gu}{stop.routes ? ` · ${stop.routes}개 노선 경유` : ''}</div>

      <div className="price-card">
        <div className="price-card__label">실제 광고가</div>
        <div className="price-card__big">약 {manWon(stop.price)}<span className="unit">원</span></div>
        <div className="price-card__sub">{won(stop.price)} / 면 · 월</div>
      </div>

      <div className="metrics">
        <div className="metric">
          <Users size={15} className="metric__ic" />
          <div className="metric__num">{stop.riders != null ? stop.riders.toLocaleString('ko-KR') : '—'}</div>
          <div className="metric__lbl">일 이용객(승하차)</div>
        </div>
        <div className="metric metric--accent">
          <Coins size={15} className="metric__ic" />
          <div className="metric__num">{stop.costPerRider != null ? `${stop.costPerRider.toLocaleString('ko-KR')}원` : '—'}</div>
          <div className="metric__lbl">이용객당 월 단가</div>
        </div>
      </div>

      {topPct != null && (
        <p className="value-line">
          이 정류장은 서울 전체에서 <b>노출 대비 가격이 싼 순으로 상위 {topPct}%</b>입니다.
          이용객 수 대비 광고가가 {stop.valuePct! >= 55 ? '저렴한' : '높은'} 편이에요.
        </p>
      )}

      {gridCell && (
        <>
          <div className="section-title">이 위치의 가격을 만든 요인</div>
          <p className="section-hint">인근 도시 구조가 광고가를 올린(▲) / 내린(▼) 정도</p>
          <FactorBars factors={gridCell.factors} />
        </>
      )}

      <p className="disclaimer">
        ‘일 이용객’은 버스 <b>승하차 인원</b>(노출 추정용 프록시)이며 실제 광고 노출수가 아닙니다.
        광고가는 덕플레이스 수집가(추정 호가)이고 단위는 <b>1면 기준 월 단가</b>입니다.
      </p>
    </div>
  )
}
