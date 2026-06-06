// Converts model/data files -> public/*.json (compact, self-contained).
//   grid.json       ← model/grid_250m.csv          (value surface + nearest ad-stop dist)
//   stops.json      ← data/seoul/모델테이블.csv      (ad inventory + 가성비 + target POI + 적정성)
//   candidates.json ← 서울시버스정류소위치정보.xlsx   (non-ad bus stops + "신설 시 예상 가치")
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'
import XLSX from 'xlsx'

const here = dirname(fileURLToPath(import.meta.url))
const OUT_DIR = resolve(here, '../public')
mkdirSync(OUT_DIR, { recursive: true })
const D = (p) => resolve(here, '../..', p)
const kb = (obj) => (Buffer.byteLength(JSON.stringify(obj)) / 1024).toFixed(0)

function parseCSV(text) {
  const rows = []
  let row = [], field = '', inQ = false
  for (let i = 0; i < text.length; i++) {
    const c = text[i]
    if (inQ) { if (c === '"') { if (text[i + 1] === '"') { field += '"'; i++ } else inQ = false } else field += c }
    else if (c === '"') inQ = true
    else if (c === ',') { row.push(field); field = '' }
    else if (c === '\n') { row.push(field); rows.push(row); row = []; field = '' }
    else if (c === '\r') { /* skip */ }
    else field += c
  }
  if (field.length || row.length) { row.push(field); rows.push(row) }
  return rows
}
const num = (s) => { const n = parseFloat(s); return Number.isFinite(n) ? n : null }

// ---- 1) parse ad stops (모델테이블) ----------------------------------------
const mt = parseCSV(readFileSync(D('data/seoul/모델테이블.csv'), 'utf8').replace(/^﻿/, ''))
const mh = mt[0]
const mc = (n) => mh.indexOf(n)
const MC = {
  ars: mc('ARS'), gu: mc('자치구'), name: mc('정류장이름'), price: mc('가격_원per면'),
  lng: mc('경도'), lat: mc('위도'), riders: mc('승하차_일평균'), routes: mc('경유노선수'), poi: mc('POI_total_300m'),
  edu: mc('POI_교육_300m'), lodg: mc('POI_숙박_300m'), art: mc('POI_예술·스포츠_300m'),
  food: mc('POI_음식_300m'), tech: mc('POI_과학·기술_300m'), med: mc('POI_보건의료_300m'), retail: mc('POI_소매_300m'),
}
const adStops = []
const adArs = new Set()
const stopLL = []
for (let r = 1; r < mt.length; r++) {
  const v = mt[r]
  if (!v[MC.ars]) continue
  const lat = num(v[MC.lat]), lng = num(v[MC.lng]), price = num(v[MC.price])
  if (lat == null || lng == null || price == null) continue
  const riders = num(v[MC.riders])
  adArs.add(String(v[MC.ars]))
  stopLL.push([lat, lng])
  adStops.push({
    a: String(v[MC.ars]), n: (v[MC.name] || '').replace(/\[\d+\]/g, '').replace(/\s{2,}/g, ' ').trim(), g: v[MC.gu],
    la: Math.round(lat * 1e6) / 1e6, ln: Math.round(lng * 1e6) / 1e6, p: Math.round(price),
    r: riders == null ? null : Math.round(riders), rt: num(v[MC.routes]), poi: num(v[MC.poi]),
    cpr: riders && riders > 0 ? Math.round(price / riders) : null,
    cat: {
      edu: num(v[MC.edu]) ?? 0, lodg: num(v[MC.lodg]) ?? 0, art: num(v[MC.art]) ?? 0, food: num(v[MC.food]) ?? 0,
      tech: num(v[MC.tech]) ?? 0, med: num(v[MC.med]) ?? 0, retail: num(v[MC.retail]) ?? 0,
    },
  })
}

// ---- 2) build grid cells + fast nearest-grid lookup ------------------------
const graw = readFileSync(D('model/grid_250m.csv'), 'utf8').replace(/^﻿/, '')
const glines = graw.split(/\r?\n/).filter((l) => l.length > 0)
const gh = glines[0].split(',')
const gcol = (n) => gh.indexOf(n)
const GC = {
  lat: gcol('위도'), lng: gcol('경도'), gu: gcol('자치구_근사'), price: gcol('예측가_원per면'),
  lo: gcol('하한_원'), hi: gcol('상한_원'), nearest: gcol('최근접학습정류장_m'), conf: gcol('신뢰도'),
}
const tops = [1, 2, 3, 4, 5].map((i) => ({ f: gcol(`top${i}_피처`), p: gcol(`top${i}_효과%`) }))
const gus = [], feats = []
const guIdx = (g) => { let i = gus.indexOf(g); if (i < 0) { i = gus.length; gus.push(g) } return i }
const featIdx = (f) => { let i = feats.indexOf(f); if (i < 0) { i = feats.length; feats.push(f) } return i }

const rawCells = []
for (let r = 1; r < glines.length; r++) {
  const v = glines[r].split(',')
  rawCells.push({
    la: parseFloat(v[GC.lat]), ln: parseFloat(v[GC.lng]), guRaw: v[GC.gu],
    p: Math.round(parseFloat(v[GC.price])), lo: Math.round(parseFloat(v[GC.lo])), hi: Math.round(parseFloat(v[GC.hi])),
    nm: Math.round(parseFloat(v[GC.nearest])), c: v[GC.conf], cols: v,
  })
}
// spatial hash for O(1) nearest grid
const latMin = Math.min(...rawCells.map((c) => c.la))
const lngMin = Math.min(...rawCells.map((c) => c.ln))
const latStepMode = (() => {
  const counts = new Map(), s = [...new Set(rawCells.map((c) => c.la))].sort((a, b) => a - b)
  for (let i = 1; i < s.length; i++) { const d = Math.round((s[i] - s[i - 1]) * 1e6) / 1e6; if (d > 0 && d < 0.01) counts.set(d, (counts.get(d) || 0) + 1) }
  return [...counts.entries()].sort((a, b) => b[1] - a[1])[0][0]
})()
const lngStepMode = (() => {
  const counts = new Map(), s = [...new Set(rawCells.map((c) => c.ln))].sort((a, b) => a - b)
  for (let i = 1; i < s.length; i++) { const d = Math.round((s[i] - s[i - 1]) * 1e6) / 1e6; if (d > 0 && d < 0.01) counts.set(d, (counts.get(d) || 0) + 1) }
  return [...counts.entries()].sort((a, b) => b[1] - a[1])[0][0]
})()
const cellHash = new Map()
const keyOf = (lat, lng) => `${Math.round((lat - latMin) / latStepMode)},${Math.round((lng - lngMin) / lngStepMode)}`
rawCells.forEach((c) => cellHash.set(keyOf(c.la, c.ln), c))
function nearestGrid(lat, lng, maxM = 320) {
  const i0 = Math.round((lat - latMin) / latStepMode), j0 = Math.round((lng - lngMin) / lngStepMode)
  const cosLat = Math.cos((lat * Math.PI) / 180)
  let best = null, bestD2 = Infinity
  for (let di = -1; di <= 1; di++) for (let dj = -1; dj <= 1; dj++) {
    const c = cellHash.get(`${i0 + di},${j0 + dj}`)
    if (!c) continue
    const dy = (c.la - lat) * 111_320, dx = (c.ln - lng) * 111_320 * cosLat
    const d2 = dy * dy + dx * dx
    if (d2 < bestD2) { bestD2 = d2; best = c }
  }
  return best && Math.sqrt(bestD2) <= maxM ? best : null
}
function nearestStopM(lat, lng) {
  const cosLat = Math.cos((lat * Math.PI) / 180)
  let best = Infinity
  for (const [sla, sln] of stopLL) {
    const dy = (sla - lat) * 111_320, dx = (sln - lng) * 111_320 * cosLat
    const d2 = dy * dy + dx * dx
    if (d2 < best) best = d2
  }
  return Math.round(Math.sqrt(best))
}

// ---- 3) write grid.json ----------------------------------------------------
;(function writeGrid() {
  const cells = rawCells.map((c) => {
    const f = []
    for (const t of tops) { const name = c.cols[t.f]; if (name) f.push([featIdx(name), Math.round(parseFloat(c.cols[t.p]) * 10) / 10]) }
    return {
      la: Math.round(c.la * 1e6) / 1e6, ln: Math.round(c.ln * 1e6) / 1e6, g: guIdx(c.guRaw),
      p: c.p, lo: c.lo, hi: c.hi, nm: c.nm, c: c.c, f, sd: nearestStopM(c.la, c.ln),
    }
  })
  const lats = cells.map((c) => c.la), lngs = cells.map((c) => c.ln)
  const out = { meta: { count: cells.length, latStep: latStepMode, lngStep: lngStepMode, bounds: [Math.min(...lngs), Math.min(...lats), Math.max(...lngs), Math.max(...lats)] }, gus, feats, cells }
  writeFileSync(resolve(OUT_DIR, 'grid.json'), JSON.stringify(out))
  console.log(`✓ grid.json — ${cells.length} cells, ${kb(out)} KB`)
})()

// ---- 4) enrich ad stops with 적정성(verdict) & write stops.json -------------
;(function writeStops() {
  for (const s of adStops) {
    const g = nearestGrid(s.la, s.ln)
    if (g) { s.pv = g.p; s.vd = s.p < g.lo ? 0 : s.p > g.hi ? 2 : 1 } // 0 저평가 1 적정 2 고평가
    else { s.pv = null; s.vd = null }
  }
  const withR = adStops.filter((s) => s.cpr != null)
  ;[...withR].sort((a, b) => a.cpr - b.cpr).forEach((s, i) => { s.vp = Math.round((1 - i / (withR.length - 1)) * 100) })
  ;[...withR].sort((a, b) => a.r - b.r).forEach((s, i) => { s.ep = Math.round((i / (withR.length - 1)) * 100) })
  ;[...withR].sort((a, b) => a.p - b.p).forEach((s, i) => { s.pp = Math.round((i / (withR.length - 1)) * 100) })
  const q = (arr, ps) => { const s = [...arr].sort((a, b) => a - b), n = s.length; return ps.map((p) => s[Math.min(n - 1, Math.floor((p / 100) * n))]) }
  const out = {
    meta: { count: adStops.length, withRiders: withR.length, priceQ: q(adStops.map((s) => s.p), [10, 50, 90]), cprQ: q(withR.map((s) => s.cpr), [10, 50, 90]), riderQ: q(withR.map((s) => s.r), [10, 50, 90]) },
    stops: adStops,
  }
  writeFileSync(resolve(OUT_DIR, 'stops.json'), JSON.stringify(out))
  console.log(`✓ stops.json — ${adStops.length} stops, ${kb(out)} KB`)
})()

// ---- 5) candidates.json — non-ad road bus stops + 신설 시 예상 가치 ----------
;(function writeCandidates() {
  const ROAD = new Set(['일반차로', '중앙차로', '가로변시간', '가로변전일'])
  const master = XLSX.utils.sheet_to_json(XLSX.readFile(D('data/seoul/서울시버스정류소위치정보(20260506).xlsx')).Sheets['Data'], { defval: '' })
  const cand = []
  for (const m of master) {
    if (adArs.has(String(m.ARS_ID))) continue
    if (!ROAD.has(m['정류소타입'])) continue
    const lat = num(m.Y좌표), lng = num(m.X좌표)
    if (lat == null || lng == null) continue
    const g = nearestGrid(lat, lng, 300)
    if (!g) continue // outside value surface
    cand.push({
      a: String(m.ARS_ID), n: (m['정류소명'] || '').replace(/\[\d+\]/g, '').trim(), g: g.guRaw,
      la: Math.round(lat * 1e6) / 1e6, ln: Math.round(lng * 1e6) / 1e6,
      pv: g.p, lo: g.lo, hi: g.hi, // 신설 시 예상 광고가
      conf: g.c,
    })
  }
  cand.sort((a, b) => b.pv - a.pv) // 신설 가치 높은 순
  const pvs = cand.map((c) => c.pv).sort((a, b) => a - b)
  const out = { meta: { count: cand.length, pvQ: [10, 50, 90].map((p) => pvs[Math.floor((p / 100) * pvs.length)]) }, candidates: cand }
  writeFileSync(resolve(OUT_DIR, 'candidates.json'), JSON.stringify(out))
  console.log(`✓ candidates.json — ${cand.length} non-ad road stops, ${kb(out)} KB`)
})()
