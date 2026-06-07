import { useEffect, useMemo, useState } from 'react'
import type { StopsData } from '../lib/stops'
import { planBasket, TARGETS } from '../lib/stops'
import { manWon } from '../lib/format'

type Props = {
  data: StopsData
  gu: string | null
  onBasket: (idxs: number[]) => void
  onSelect: (idx: number) => void
  selectedIdx: number | null
}

export default function BudgetPlanner({ data, gu, onBasket, onSelect, selectedIdx }: Props) {
  const [man, setMan] = useState('500')
  const [target, setTarget] = useState('all')
  const budget = (parseInt(man.replace(/[^\d]/g, ''), 10) || 0) * 10_000
  const isTargeted = target !== 'all'

  const result = useMemo(
    () => (budget > 0 ? planBasket(data.stops, budget, gu, target) : null),
    [data, budget, gu, target],
  )

  useEffect(() => {
    onBasket(result ? result.picked.map((s) => s.idx) : [])
  }, [result, onBasket])

  return (
    <div className="panel-body">
      <p className="section-hint" style={{ marginTop: 0 }}>
        {isTargeted
          ? <>예산 안에서 <b>타겟 관련 정류장 중 가성비 좋은</b> 조합을 골라줍니다.</>
          : <>예산 안에서 <b>이용객(노출) 대비 가성비 좋은</b> 정류장 조합을 골라줍니다.</>}
      </p>

      <div className="plan-input">
        <label>월 예산</label>
        <div className="plan-input__row">
          <input inputMode="numeric" value={man} onChange={(e) => setMan(e.target.value)} placeholder="500" />
          <span>만원{gu ? ` · ${gu}` : ' · 서울 전체'}</span>
        </div>
      </div>

      <div className="target">
        <label className="target__label">광고 타겟 <em>(POI 기반 추정)</em></label>
        <div className="target__chips">
          {TARGETS.map((t) => (
            <button
              key={t.key}
              className={`chip ${target === t.key ? 'on' : ''}`}
              onClick={() => setTarget(t.key)}
              title={t.desc}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {result && (
        <>
          <div className="plan-stats">
            <div className="plan-stat">
              <div className="plan-stat__num">{result.picked.length}곳</div>
              <div className="plan-stat__lbl">정류장</div>
            </div>
            <div className="plan-stat">
              <div className="plan-stat__num">{manWon(result.totalCost)}원</div>
              <div className="plan-stat__lbl">월 집행액</div>
            </div>
            <div className="plan-stat plan-stat--accent">
              <div className="plan-stat__num">{result.totalRiders.toLocaleString('ko-KR')}</div>
              <div className="plan-stat__lbl">{isTargeted ? '타겟 일 노출(추정)' : '일 노출 합(승하차)'}</div>
            </div>
          </div>

          <div className="rank__list" style={{ marginTop: 14 }}>
            {result.picked.slice(0, 80).map((s) => (
              <button
                key={s.ars}
                className={`rank__row ${s.idx === selectedIdx ? 'on' : ''}`}
                onClick={() => onSelect(s.idx)}
              >
                <span className="rank__name">
                  {s.name}
                  <em>
                    {s.gu} · 일 {s.riders?.toLocaleString('ko-KR')}명
                    {isTargeted && ` · 적합도 ${Math.round((s.targetAff[target] ?? 0) * 100)}%`}
                  </em>
                </span>
                <span className="rank__cpr">
                  {Math.round(s.price / 10000)}만원
                  <em>{s.costPerRider?.toLocaleString('ko-KR')}원/명</em>
                </span>
              </button>
            ))}
          </div>
          {!result.picked.length && (
            <p className="note-warn">예산이 한 정류장 단가보다 작아요. 예산을 늘려보세요.</p>
          )}
        </>
      )}

      <p className="disclaimer">
        타겟은 인구통계 실측이 아니라 <b>주변 업종(POI) 구성으로 추정</b>한 값입니다. 정류장 통째 구매를 가정한
        단순 그리디 추천이며 중복 도달은 고려하지 않습니다. ‘노출’은 승하차 인원(프록시)입니다.
      </p>
    </div>
  )
}
