import { useMemo } from 'react'
import type { StopsData } from '../lib/stops'

type Props = {
  data: StopsData
  gu: string | null
  selectedIdx: number | null
  onSelect: (idx: number) => void
}

export default function ValueRanking({ data, gu, selectedIdx, onSelect }: Props) {
  const ranked = useMemo(
    () =>
      data.stops
        .filter((s) => s.costPerRider != null && (!gu || s.gu === gu))
        .sort((a, b) => (a.costPerRider as number) - (b.costPerRider as number))
        .slice(0, 60),
    [data, gu],
  )

  return (
    <div className="rank">
      <p className="rank__hint">
        이용객(승하차) 대비 광고가가 <b>싼 순</b>. 위로 갈수록 ‘목 좋은데 싼’ 자리예요.
      </p>
      <div className="rank__head">
        <span>정류장</span>
        <span>이용객당 단가</span>
      </div>
      <div className="rank__list">
        {ranked.map((s, i) => (
          <button
            key={s.ars}
            className={`rank__row ${s.idx === selectedIdx ? 'on' : ''}`}
            onClick={() => onSelect(s.idx)}
          >
            <span className="rank__no">{i + 1}</span>
            <span className="rank__name">
              {s.name}
              <em>{s.gu} · 일 {s.riders?.toLocaleString('ko-KR')}명</em>
            </span>
            <span className="rank__cpr">
              {s.costPerRider?.toLocaleString('ko-KR')}원
              <em>{Math.round(s.price / 10000)}만원/월</em>
            </span>
          </button>
        ))}
        {!ranked.length && <p className="section-hint">해당 지역 데이터가 없어요.</p>}
      </div>
    </div>
  )
}
