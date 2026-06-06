// Grid data: load grid.json, build a GeoJSON of 250m squares, nearest-cell lookup.

export type Factor = { name: string; pct: number }
export type Cell = {
  lat: number
  lng: number
  gu: string
  price: number
  lo: number
  hi: number
  nearestM: number
  conf: '상' | '중' | '하'
  factors: Factor[]
  idx: number
  stopDist: number // 최근접 광고 정류장까지 거리(m) — 공백 탐지용
}

type RawGrid = {
  meta: { count: number; latStep: number; lngStep: number; bounds: [number, number, number, number] }
  gus: string[]
  feats: string[]
  cells: { la: number; ln: number; g: number; p: number; lo: number; hi: number; nm: number; c: string; f: [number, number][]; sd: number }[]
}

export type GridData = {
  cells: Cell[]
  gus: string[]
  latStep: number
  lngStep: number
  bounds: [number, number, number, number]
  geojson: GeoJSON.FeatureCollection
  guCentroids: Record<string, [number, number]>
}

export async function loadGrid(url: string): Promise<GridData> {
  const res = await fetch(url)
  if (!res.ok) throw new Error(`grid.json 로드 실패 (${res.status})`)
  const raw: RawGrid = await res.json()
  const { latStep, lngStep, bounds } = raw.meta

  const cells: Cell[] = raw.cells.map((c, i) => ({
    lat: c.la,
    lng: c.ln,
    gu: raw.gus[c.g],
    price: c.p,
    lo: c.lo,
    hi: c.hi,
    nearestM: c.nm,
    conf: c.c as Cell['conf'],
    factors: c.f.map(([fi, pct]) => ({ name: raw.feats[fi], pct })),
    idx: i,
    stopDist: c.sd,
  }))

  const hLat = latStep / 2
  const hLng = lngStep / 2
  const features: GeoJSON.Feature[] = cells.map((c) => ({
    type: 'Feature',
    properties: { idx: c.idx, p: c.price, conf: c.conf },
    geometry: {
      type: 'Polygon',
      coordinates: [[
        [c.lng - hLng, c.lat - hLat],
        [c.lng + hLng, c.lat - hLat],
        [c.lng + hLng, c.lat + hLat],
        [c.lng - hLng, c.lat + hLat],
        [c.lng - hLng, c.lat - hLat],
      ]],
    },
  }))

  // district centroids (mean of member cell centers) for the "fly to gu" control
  const acc: Record<string, { x: number; y: number; n: number }> = {}
  for (const c of cells) {
    const a = (acc[c.gu] ||= { x: 0, y: 0, n: 0 })
    a.x += c.lng
    a.y += c.lat
    a.n += 1
  }
  const guCentroids: Record<string, [number, number]> = {}
  for (const [gu, a] of Object.entries(acc)) guCentroids[gu] = [a.x / a.n, a.y / a.n]

  return {
    cells,
    gus: [...raw.gus].sort((a, b) => a.localeCompare(b, 'ko')),
    latStep,
    lngStep,
    bounds,
    geojson: { type: 'FeatureCollection', features },
    guCentroids,
  }
}

// "공백 핫스팟" = 가치(예측가)는 높은데 인근에 광고 정류장이 없는 칸 → 신설 후보.
export function gapHotspots(data: GridData, minPriceQ = 0.7, minDist = 450): {
  fc: GeoJSON.FeatureCollection; count: number
} {
  const prices = data.cells.map((c) => c.price).sort((a, b) => a - b)
  const thr = prices[Math.floor(prices.length * minPriceQ)]
  const cells = data.cells.filter((c) => c.price >= thr && c.stopDist >= minDist)
  return {
    fc: {
      type: 'FeatureCollection',
      features: cells.map((c) => ({
        type: 'Feature',
        properties: { p: c.price },
        geometry: { type: 'Point', coordinates: [c.lng, c.lat] },
      })),
    },
    count: cells.length,
  }
}

// Nearest grid cell to a clicked point. Returns null if the click is too far
// from any cell (e.g. river / outside Seoul coverage).
const MAX_SNAP_M = 220
export function nearestCell(data: GridData, lat: number, lng: number): Cell | null {
  const cosLat = Math.cos((lat * Math.PI) / 180)
  let best: Cell | null = null
  let bestD2 = Infinity
  for (const c of data.cells) {
    const dy = (c.lat - lat) * 111_320
    const dx = (c.lng - lng) * 111_320 * cosLat
    const d2 = dx * dx + dy * dy
    if (d2 < bestD2) {
      bestD2 = d2
      best = c
    }
  }
  if (!best || Math.sqrt(bestD2) > MAX_SNAP_M) return null
  return best
}

// Inferno-ish heat ramp (cheap, expensive) — used for both the map fill
// expression and the legend. Stops chosen near price quantiles.
export const PRICE_STOPS: [number, string][] = [
  [250_000, '#1b1147'],
  [350_000, '#5a1a6e'],
  [480_000, '#9a2865'],
  [640_000, '#cf4446'],
  [880_000, '#ee6a24'],
  [1_100_000, '#f9a52c'],
  [1_500_000, '#fbe154'],
]

export function priceColor(p: number): string {
  const s = PRICE_STOPS
  if (p <= s[0][0]) return s[0][1]
  if (p >= s[s.length - 1][0]) return s[s.length - 1][1]
  for (let i = 1; i < s.length; i++) {
    if (p <= s[i][0]) {
      const [p0, c0] = s[i - 1]
      const [p1, c1] = s[i]
      return lerpColor(c0, c1, (p - p0) / (p1 - p0))
    }
  }
  return s[s.length - 1][1]
}

function lerpColor(a: string, b: string, t: number): string {
  const pa = hex(a)
  const pb = hex(b)
  const r = Math.round(pa[0] + (pb[0] - pa[0]) * t)
  const g = Math.round(pa[1] + (pb[1] - pa[1]) * t)
  const bl = Math.round(pa[2] + (pb[2] - pa[2]) * t)
  return `rgb(${r},${g},${bl})`
}
function hex(h: string): [number, number, number] {
  const n = parseInt(h.slice(1), 16)
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255]
}
