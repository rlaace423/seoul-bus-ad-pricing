import { useCallback, useEffect, useMemo, useState } from 'react'
import { Building2, Megaphone, Flame, SquareStack, PlusCircle, Gauge, Wallet, Layers } from 'lucide-react'
import { loadGrid, nearestCell, type GridData, type Cell } from './lib/grid'
import { loadStops, type StopsData } from './lib/stops'
import { loadCandidates, type CandidatesData } from './lib/candidates'
import MapView, { type PointLayer, type ClickTarget } from './components/MapView'
import StopCard from './components/StopCard'
import AdStopCard from './components/AdStopCard'
import CandidateCard from './components/CandidateCard'
import CandidateRanking from './components/CandidateRanking'
import ValueRanking from './components/ValueRanking'
import BudgetPlanner from './components/BudgetPlanner'
import InfoPanel from './components/InfoPanel'
import Legend from './components/Legend'

type Persona = 'city' | 'adv'
type CityMode = 'heat' | 'adstops' | 'cand'
type AdvMode = 'value' | 'budget'

const CITY_MODES: { id: CityMode; label: string; Icon: typeof Flame }[] = [
  { id: 'heat', label: '가치 히트맵', Icon: Flame },
  { id: 'adstops', label: '현재 광고판', Icon: SquareStack },
  { id: 'cand', label: '신설 후보', Icon: PlusCircle },
]
const ADV_MODES: { id: AdvMode; label: string; Icon: typeof Gauge }[] = [
  { id: 'value', label: '가성비', Icon: Gauge },
  { id: 'budget', label: '예산 플래너', Icon: Wallet },
]

export default function App() {
  const [grid, setGrid] = useState<GridData | null>(null)
  const [stops, setStops] = useState<StopsData | null>(null)
  const [cands, setCands] = useState<CandidatesData | null>(null)
  const [error, setError] = useState<string | null>(null)

  const [persona, setPersona] = useState<Persona>('city')
  const [cityMode, setCityMode] = useState<CityMode>('heat')
  const [advMode, setAdvMode] = useState<AdvMode>('value')

  const [gridSel, setGridSel] = useState<Cell | null>(null)
  const [adSel, setAdSel] = useState<number | null>(null)
  const [candSel, setCandSel] = useState<number | null>(null)
  const [basket, setBasket] = useState<number[]>([])
  const [gu, setGu] = useState<string | null>(null)
  const [flyTo, setFlyTo] = useState<[number, number] | null>(null)
  const [showHeat, setShowHeat] = useState(false)

  useEffect(() => {
    Promise.all([loadGrid('./grid.json'), loadStops('./stops.json'), loadCandidates('./candidates.json')])
      .then(([g, s, c]) => { setGrid(g); setStops(s); setCands(c) })
      .catch((e) => setError(String(e)))
  }, [])

  const onPickGrid = useCallback((lat: number, lng: number) => { if (grid) setGridSel(nearestCell(grid, lat, lng)) }, [grid])
  const selectAd = useCallback((idx: number, fly: boolean) => {
    setAdSel(idx); if (fly && stops) { const s = stops.stops[idx]; setFlyTo([s.lng, s.lat]) }
  }, [stops])
  const selectCand = useCallback((idx: number, fly: boolean) => {
    setCandSel(idx); if (fly && cands) { const c = cands.list[idx]; setFlyTo([c.lng, c.lat]) }
  }, [cands])
  const onBasket = useCallback((idxs: number[]) => setBasket(idxs), [])

  const adGridCell = useMemo(() => {
    if (adSel == null || !grid || !stops) return null
    const s = stops.stops[adSel]; return nearestCell(grid, s.lat, s.lng)
  }, [adSel, grid, stops])
  const candGridCell = useMemo(() => {
    if (candSel == null || !grid || !cands) return null
    const c = cands.list[candSel]; return nearestCell(grid, c.lat, c.lng)
  }, [candSel, grid, cands])
  const verdictCounts = useMemo(() => {
    const acc = { 0: 0, 1: 0, 2: 0 }
    stops?.stops.forEach((s) => { if (s.verdict != null) acc[s.verdict]++ })
    return acc
  }, [stops])

  if (error) return <div className="fatal">데이터를 불러오지 못했습니다.<br />{error}</div>
  if (!grid || !stops || !cands) return <div className="loading">서울 격자·정류장 데이터 불러오는 중…</div>

  // ---- map config derived from persona + mode ----
  let heat = { on: false, opacity: 0.5 }
  let pointLayer: PointLayer = 'none'
  let clickTarget: ClickTarget = 'grid'
  if (persona === 'city') {
    if (cityMode === 'heat') { heat = { on: true, opacity: 0.58 }; pointLayer = 'none'; clickTarget = 'grid' }
    else if (cityMode === 'adstops') { heat = { on: true, opacity: 0.18 }; pointLayer = 'adVerdict'; clickTarget = 'ad' }
    else { heat = { on: true, opacity: 0.16 }; pointLayer = 'cand'; clickTarget = 'cand' }
  } else {
    heat = { on: showHeat, opacity: 0.4 }; pointLayer = 'adValue'; clickTarget = 'ad'
  }

  const legendMode = persona === 'adv' ? 'value' : cityMode === 'heat' ? 'price' : cityMode === 'adstops' ? 'verdict' : 'candval'

  return (
    <div className="app">
      <aside className="sidebar">
        <header className="brand">
          <div className="brand__kicker">DATA-DRIVEN URBAN DESIGN</div>
          <h1 className="brand__title">버스정류장 광고가, 도시 구조로 읽다</h1>
        </header>

        <div className="persona">
          <button className={persona === 'city' ? 'on' : ''} onClick={() => setPersona('city')}>
            <Building2 size={16} /> 도시 설계
          </button>
          <button className={persona === 'adv' ? 'on' : ''} onClick={() => setPersona('adv')}>
            <Megaphone size={16} /> 광고주
          </button>
        </div>

        <div className="controls">
          <div className="seg seg--3">
            {persona === 'city'
              ? CITY_MODES.map(({ id, label, Icon }) => (
                <button key={id} className={cityMode === id ? 'on' : ''} onClick={() => setCityMode(id)}>
                  <Icon size={14} strokeWidth={2.2} /> {label}
                </button>))
              : ADV_MODES.map(({ id, label, Icon }) => (
                <button key={id} className={advMode === id ? 'on' : ''} onClick={() => setAdvMode(id)}>
                  <Icon size={14} strokeWidth={2.2} /> {label}
                </button>))}
          </div>
          <select className="gu-select" value={gu ?? ''} onChange={(e) => {
            const v = e.target.value || null; setGu(v)
            if (v) { const c = grid.guCentroids[v]; if (c) setFlyTo([c[0], c[1]]) }
          }}>
            <option value="">서울 전체</option>
            {grid.gus.map((g) => <option key={g} value={g}>{g}</option>)}
          </select>
        </div>

        <div className="content">
          {persona === 'city' ? (
            cityMode === 'heat' ? (
              gridSel ? <InfoPanel cell={gridSel} /> : <Empty text="지도에서 위치를 클릭하면 예상 광고가와 ‘왜 그 가격인지’를 도시 구조로 설명합니다." />
            ) : cityMode === 'adstops' ? (
              adSel != null ? <AdStopCard stop={stops.stops[adSel]} gridCell={adGridCell} />
                : <Empty text="현재 광고가 걸린 정류장의 실제가가 예측 적정가 대비 적정한지 색으로 보여줍니다. 점을 클릭해 비교해 보세요."
                    badge={`저평가 ${verdictCounts[0]} · 적정 ${verdictCounts[1]} · 고평가 ${verdictCounts[2]}`} />
            ) : (
              <>
                {candSel != null && <CandidateCard key={candSel} cand={cands.list[candSel]} gridCell={candGridCell} />}
                <CandidateRanking data={cands} gu={gu} selectedIdx={candSel} onSelect={(i) => selectCand(i, true)} />
              </>
            )
          ) : (
            <>
              {adSel != null && <StopCard key={adSel} stop={stops.stops[adSel]} gridCell={adGridCell} />}
              {advMode === 'value'
                ? <ValueRanking data={stops} gu={gu} selectedIdx={adSel} onSelect={(i) => selectAd(i, true)} />
                : <BudgetPlanner data={stops} gu={gu} onBasket={onBasket} selectedIdx={adSel} onSelect={(i) => selectAd(i, true)} />}
            </>
          )}
        </div>

        <footer className="credit">예측: XGBoost · SHAP · 서울 2,553개 광고 정류장 학습 · 8조</footer>
      </aside>

      <main className="stage">
        <MapView
          grid={grid} stops={stops} cands={cands}
          heat={heat} pointLayer={pointLayer} clickTarget={clickTarget}
          selectedAd={persona === 'adv' || cityMode === 'adstops' ? adSel : null}
          selectedCand={persona === 'city' && cityMode === 'cand' ? candSel : null}
          basket={persona === 'adv' && advMode === 'budget' ? basket : []}
          gridSel={persona === 'city' && cityMode === 'heat' ? gridSel : null}
          flyTo={flyTo}
          onPickGrid={onPickGrid} onPickAd={(i) => selectAd(i, false)} onPickCand={(i) => selectCand(i, false)}
        />
        {persona === 'adv' && (
          <button className={`heat-toggle ${showHeat ? 'on' : ''}`} onClick={() => setShowHeat((v) => !v)}>
            <Layers size={15} strokeWidth={2.2} /> 가격 히트맵 {showHeat ? '끄기' : '켜기'}
          </button>
        )}
        <Legend mode={legendMode} />
      </main>
    </div>
  )
}

function Empty({ text, badge }: { text: string; badge?: string }) {
  return (
    <div className="empty">
      <p>{text}</p>
      {badge && <div className="empty__badge">{badge}</div>}
    </div>
  )
}
