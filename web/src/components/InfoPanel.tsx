import type { Cell } from '../lib/grid'
import { manWon, won } from '../lib/format'
import FactorBars from './FactorBars'
import ConfBadge from './ConfBadge'

export default function InfoPanel({ cell }: { cell: Cell }) {
  return (
    <div className="panel-body">
      <div className="row-between">
        <span className="gu">{cell.gu}</span>
        <ConfBadge conf={cell.conf} nearestM={cell.nearestM} />
      </div>

      <div className="price-card">
        <div className="price-card__label">예상 적정 광고가</div>
        <div className="price-card__big">약 {manWon(cell.price)}<span className="unit">원</span></div>
        <div className="price-card__sub">{won(cell.price)} / 면 · 월</div>
        <div className="price-card__range">
          <span>80% 예상 범위</span>
          <b>{manWon(cell.lo)} ~ {manWon(cell.hi)}원</b>
        </div>
      </div>

      <div className="section-title">이 가격을 만든 요인</div>
      <p className="section-hint">위치의 도시 구조가 광고가를 올린(▲) / 내린(▼) 정도</p>
      <FactorBars factors={cell.factors} />

      <p className="disclaimer">
        예측가는 실거래가가 아닌 <b>추정 호가</b>이며, 단위는 <b>1면 기준 월 단가</b>입니다.
        외곽·데이터 희소 지역(신뢰도 ‘하’)은 참고용으로만 보세요.
      </p>
    </div>
  )
}
