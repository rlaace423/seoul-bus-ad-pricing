// 신설 후보: 광고가 없는 실제 버스정류장(도로변) + "신설 시 예상 광고가".
export type Candidate = {
  idx: number
  ars: string
  name: string
  gu: string
  lat: number
  lng: number
  predValue: number // 신설 시 예상 광고가 (원/면·월)
  lo: number
  hi: number
  conf: '상' | '중' | '하'
}

export type CandidatesData = {
  list: Candidate[] // 신설 가치 높은 순 정렬됨
  gus: string[]
  geojson: GeoJSON.FeatureCollection
  pvQ: number[]
}

type RawCand = { a: string; n: string; g: string; la: number; ln: number; pv: number; lo: number; hi: number; conf: string }

export async function loadCandidates(url: string): Promise<CandidatesData> {
  const res = await fetch(url)
  if (!res.ok) throw new Error(`candidates.json 로드 실패 (${res.status})`)
  const raw: { meta: { pvQ: number[] }; candidates: RawCand[] } = await res.json()
  const list: Candidate[] = raw.candidates.map((c, i) => ({
    idx: i, ars: c.a, name: c.n, gu: c.g, lat: c.la, lng: c.ln,
    predValue: c.pv, lo: c.lo, hi: c.hi, conf: c.conf as Candidate['conf'],
  }))
  const features: GeoJSON.Feature[] = list.map((c) => ({
    type: 'Feature',
    properties: { idx: c.idx, pv: c.predValue },
    geometry: { type: 'Point', coordinates: [c.lng, c.lat] },
  }))
  const gus = [...new Set(list.map((c) => c.gu))].sort((a, b) => a.localeCompare(b, 'ko'))
  return { list, gus, geojson: { type: 'FeatureCollection', features }, pvQ: raw.meta.pvQ }
}

export function nearestCandidate(data: CandidatesData, lat: number, lng: number, maxM = 200): Candidate | null {
  const cosLat = Math.cos((lat * Math.PI) / 180)
  let best: Candidate | null = null, bestD2 = Infinity
  for (const c of data.list) {
    const dy = (c.lat - lat) * 111_320, dx = (c.lng - lng) * 111_320 * cosLat
    const d2 = dx * dx + dy * dy
    if (d2 < bestD2) { bestD2 = d2; best = c }
  }
  return best && Math.sqrt(bestD2) <= maxM ? best : null
}
