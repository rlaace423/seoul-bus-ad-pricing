import { PlusCircle } from 'lucide-react'
import type { Candidate } from '../lib/candidates'
import type { Cell } from '../lib/grid'
import { manWon, won } from '../lib/format'
import FactorBars from './FactorBars'
import ConfBadge from './ConfBadge'

export default function CandidateCard({ cand, gridCell }: { cand: Candidate; gridCell: Cell | null }) {
  return (
    <div className="panel-body">
      <div className="row-between">
        <span className="gu">{cand.name}</span>
        <ConfBadge conf={cand.conf} nearestM={0} />
      </div>
      <div className="stop-gu">{cand.gu} · 현재 광고판 없음</div>

      <div className="price-card price-card--cand">
        <div className="price-card__label"><PlusCircle size={13} style={{ verticalAlign: -2, marginRight: 4 }} />신설 시 예상 광고가</div>
        <div className="price-card__big">약 {manWon(cand.predValue)}<span className="unit">원</span></div>
        <div className="price-card__sub">{won(cand.predValue)} / 면 · 월</div>
        <div className="price-card__range">
          <span>80% 예상 범위</span>
          <b>{manWon(cand.lo)} ~ {manWon(cand.hi)}원</b>
        </div>
      </div>

      {gridCell && (
        <>
          <div className="section-title">이 위치의 가치를 만든 요인</div>
          <p className="section-hint">도시 구조가 예상 광고가를 올린(▲) / 내린(▼) 정도</p>
          <FactorBars factors={gridCell.factors} />
        </>
      )}

      <p className="disclaimer">
        실제 버스정류장(도로변)이지만 광고판이 없는 곳입니다. ‘신설 시 예상 광고가’는 인근 도시 구조로 추정한
        값(추정 호가, 1면·월)이며 설치 가능 여부·비용은 별도입니다.
      </p>
    </div>
  )
}
