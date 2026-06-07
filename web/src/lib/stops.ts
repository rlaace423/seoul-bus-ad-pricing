// Real ad inventory: 2,553 Seoul bus stops with actual price + exposure proxy + value metrics.

export type Stop = {
  idx: number
  ars: string
  name: string
  gu: string
  lat: number
  lng: number
  price: number // 실제 광고가 (원/면·월)
  riders: number | null // 승하차 일평균 (노출 프록시)
  routes: number | null
  poi: number | null
  costPerRider: number | null // ₩ / 일 이용객
  valuePct: number | null // 가성비 백분위 (100 = 노출 대비 가장 쌈)
  exposurePct: number | null
  pricePct: number | null
  cat: CatPOI // 타겟 오디언스 프록시 (300m POI)
  targetAff: Record<string, number> // 타겟별 적합도 0~1
  predValue: number | null // 인근 격자 예측 적정가
  verdict: 0 | 1 | 2 | null // 0 저평가 / 1 적정 / 2 고평가 (실제가 vs 예측범위)
}

export type CatPOI = { edu: number; lodg: number; art: number; food: number; tech: number; med: number; retail: number }

// 광고 타겟(오디언스) — 인구통계 실측이 없어 300m POI 구성으로 추정.
// 데이터로 실제 변별되는 업종만 채택(소상공인 POI 검증 완료). cat=대표 업종.
export const TARGETS: { key: string; label: string; cat: keyof CatPOI | null; desc: string }[] = [
  { key: 'all', label: '전체', cat: null, desc: '타겟 없이 노출 대비 가성비순' },
  { key: 'student', label: '학원가·학생', cat: 'edu', desc: '학원·학교 밀집 (대치·노원·목동)' },
  { key: 'tourist', label: '관광·외국인', cat: 'lodg', desc: '숙박 밀집 (명동·홍대·남산)' },
  { key: 'office', label: '오피스·직장인', cat: 'tech', desc: '오피스·IT 밀집 (강남·교대·여의도)' },
  { key: 'shopping', label: '쇼핑·리테일', cat: 'retail', desc: '소매점 밀집 (명동·동대문)' },
  { key: 'medical', label: '병원·생활', cat: 'med', desc: '의료시설 밀집' },
]

export type StopsData = {
  stops: Stop[]
  withRiders: number
  gus: string[]
  geojson: GeoJSON.FeatureCollection
  meta: { priceQ: number[]; cprQ: number[]; riderQ: number[] }
}

type RawStop = {
  a: string; n: string; g: string; la: number; ln: number; p: number
  r: number | null; rt: number | null; poi: number | null
  cpr: number | null; vp?: number; ep?: number; pp?: number; cat: CatPOI
  pv: number | null; vd: 0 | 1 | 2 | null
}

export async function loadStops(url: string): Promise<StopsData> {
  const res = await fetch(url)
  if (!res.ok) throw new Error(`stops.json 로드 실패 (${res.status})`)
  const raw: { meta: StopsData['meta'] & { withRiders: number }; stops: RawStop[] } = await res.json()

  const stops: Stop[] = raw.stops.map((s, i) => ({
    idx: i, ars: s.a, name: s.n, gu: s.g, lat: s.la, lng: s.ln, price: s.p,
    riders: s.r, routes: s.rt, poi: s.poi, costPerRider: s.cpr,
    valuePct: s.vp ?? null, exposurePct: s.ep ?? null, pricePct: s.pp ?? null,
    cat: s.cat, targetAff: {}, predValue: s.pv, verdict: s.vd,
  }))

  // per-target affinity = percentile of the target's representative POI across stops (0~1)
  for (const t of TARGETS) {
    if (!t.cat) continue
    const cat = t.cat
    const scored = stops.map((s) => ({ s, v: s.cat[cat] || 0 })).sort((a, b) => a.v - b.v)
    const n = scored.length
    scored.forEach((x, i) => { x.s.targetAff[t.key] = n > 1 ? i / (n - 1) : 0.5 })
  }

  const features: GeoJSON.Feature[] = stops.map((s, i) => ({
    type: 'Feature',
    properties: { idx: i, vp: s.valuePct ?? -1, r: s.riders ?? 0, vd: s.verdict ?? -1 },
    geometry: { type: 'Point', coordinates: [s.lng, s.lat] },
  }))

  const gus = [...new Set(stops.map((s) => s.gu))].sort((a, b) => a.localeCompare(b, 'ko'))

  return {
    stops,
    withRiders: raw.meta.withRiders,
    gus,
    geojson: { type: 'FeatureCollection', features },
    meta: { priceQ: raw.meta.priceQ, cprQ: raw.meta.cprQ, riderQ: raw.meta.riderQ },
  }
}

// nearest real stop to a click (used in 가성비 mode)
export function nearestStop(data: StopsData, lat: number, lng: number, maxM = 400): Stop | null {
  const cosLat = Math.cos((lat * Math.PI) / 180)
  let best: Stop | null = null
  let bestD2 = Infinity
  for (const s of data.stops) {
    const dy = (s.lat - lat) * 111_320
    const dx = (s.lng - lng) * 111_320 * cosLat
    const d2 = dx * dx + dy * dy
    if (d2 < bestD2) { bestD2 = d2; best = s }
  }
  if (!best || Math.sqrt(bestD2) > maxM) return null
  return best
}

// diverging value color: 0 (비쌈/노출 적음, red) → 50 (yellow) → 100 (가성비 최고, green)
export const VALUE_STOPS: [number, string][] = [
  [0, '#d64545'],
  [50, '#e8c14e'],
  [100, '#3fb96b'],
]

// 전체: 가성비(₩/명)순. 타겟: 타겟 밀집도순(가성비는 동률 시 우선) — 상위 40% 적합 정류장 안에서.
// → 타겟을 바꾸면 풀과 순서가 모두 바뀌어 결과가 실제로 달라진다(관광→명동·홍대, 학생→대치·노원…).
const TARGET_CUTOFF = 0.6
export function planBasket(stops: Stop[], budget: number, gu: string | null, target: string): {
  picked: Stop[]; totalCost: number; totalRiders: number
} {
  const base = stops.filter((s) => s.costPerRider != null && (s.riders ?? 0) > 0 && (!gu || s.gu === gu))
  const pool =
    target === 'all'
      ? base.sort((a, b) => (a.costPerRider as number) - (b.costPerRider as number))
      : base
          .filter((s) => (s.targetAff[target] ?? 0) >= TARGET_CUTOFF)
          .sort((a, b) => (b.targetAff[target] ?? 0) - (a.targetAff[target] ?? 0) || (a.costPerRider as number) - (b.costPerRider as number))
  const picked: Stop[] = []
  let totalCost = 0
  let totalRiders = 0
  for (const s of pool) {
    if (totalCost + s.price > budget) continue
    picked.push(s)
    totalCost += s.price
    totalRiders += s.riders ?? 0
  }
  return { picked, totalCost, totalRiders }
}
