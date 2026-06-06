import { useMemo } from 'react'
import type { CandidatesData } from '../lib/candidates'
import { manWon } from '../lib/format'

type Props = {
  data: CandidatesData
  gu: string | null
  selectedIdx: number | null
  onSelect: (idx: number) => void
}

export default function CandidateRanking({ data, gu, selectedIdx, onSelect }: Props) {
  const ranked = useMemo(
    () => data.list.filter((c) => !gu || c.gu === gu).slice(0, 60), // 이미 신설가치순 정렬
    [data, gu],
  )

  return (
    <div className="rank">
      <p className="rank__hint">
        광고판이 <b>없는</b> 실제 버스정류장을 <b>신설 시 예상 광고가 높은 순</b>으로. 위가 설치 1순위 후보예요.
      </p>
      <div className="rank__head">
        <span>버스정류장 (광고 없음)</span>
        <span>신설 시 예상가</span>
      </div>
      <div className="rank__list">
        {ranked.map((c, i) => (
          <button key={c.ars + i} className={`rank__row ${c.idx === selectedIdx ? 'on' : ''}`} onClick={() => onSelect(c.idx)}>
            <span className="rank__no">{i + 1}</span>
            <span className="rank__name">{c.name}<em>{c.gu}</em></span>
            <span className="rank__cpr rank__cpr--val">{manWon(c.predValue)}원</span>
          </button>
        ))}
        {!ranked.length && <p className="section-hint">해당 지역 후보가 없어요.</p>}
      </div>
    </div>
  )
}
