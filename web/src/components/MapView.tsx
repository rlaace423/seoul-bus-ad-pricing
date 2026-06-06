import { useEffect, useRef } from 'react'
import maplibregl, { type StyleSpecification } from 'maplibre-gl'
import type { GridData, Cell } from '../lib/grid'
import { PRICE_STOPS } from '../lib/grid'
import type { StopsData } from '../lib/stops'
import type { CandidatesData } from '../lib/candidates'
import { manWon } from '../lib/format'

export type PointLayer = 'none' | 'adValue' | 'adVerdict' | 'cand'
export type ClickTarget = 'grid' | 'ad' | 'cand'

type Props = {
  grid: GridData
  stops: StopsData
  cands: CandidatesData
  heat: { on: boolean; opacity: number }
  pointLayer: PointLayer
  clickTarget: ClickTarget
  selectedAd: number | null
  selectedCand: number | null
  basket: number[]
  gridSel: Cell | null
  flyTo: [number, number] | null
  onPickGrid: (lat: number, lng: number) => void
  onPickAd: (idx: number) => void
  onPickCand: (idx: number) => void
}

const BASE_STYLE: StyleSpecification = {
  version: 8,
  sources: {
    carto: {
      type: 'raster',
      tiles: ['a', 'b', 'c', 'd'].map((s) => `https://${s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png`),
      tileSize: 256, attribution: '© OpenStreetMap · © CARTO',
    },
  },
  layers: [{ id: 'carto', type: 'raster', source: 'carto' }],
}

const gridColor = ['interpolate', ['linear'], ['get', 'p'], ...PRICE_STOPS.flat()]
const valueColor = ['case', ['<', ['get', 'vp'], 0], '#6b6b78',
  ['interpolate', ['linear'], ['get', 'vp'], 0, '#d64545', 50, '#e8c14e', 100, '#3fb96b']]
const verdictColor = ['match', ['get', 'vd'], 0, '#3fb96b', 1, '#7d7d8c', 2, '#ff6b5e', '#7d7d8c']
const candColor = ['interpolate', ['linear'], ['get', 'pv'], ...PRICE_STOPS.flat()]

// radius scales with both zoom and a data field
const zoomR = (field: string, lo: number, mid: number, hiv: number) => ([
  'interpolate', ['linear'], ['zoom'],
  10, ['interpolate', ['linear'], ['get', field], lo, 1.4, mid, 3, hiv, 5],
  13, ['interpolate', ['linear'], ['get', field], lo, 2.6, mid, 5.5, hiv, 9],
  16, ['interpolate', ['linear'], ['get', field], lo, 4.5, mid, 10, hiv, 16],
])

export default function MapView(props: Props) {
  const { grid, stops, cands, heat, pointLayer, clickTarget, selectedAd, selectedCand, basket, gridSel, flyTo,
    onPickGrid, onPickAd, onPickCand } = props
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<maplibregl.Map | null>(null)
  const markerRef = useRef<maplibregl.Marker | null>(null)
  const ready = useRef(false)
  const ctRef = useRef(clickTarget); ctRef.current = clickTarget
  const cbRef = useRef({ onPickGrid, onPickAd, onPickCand }); cbRef.current = { onPickGrid, onPickAd, onPickCand }

  useEffect(() => {
    if (!containerRef.current) return
    const map = new maplibregl.Map({
      container: containerRef.current, style: BASE_STYLE, bounds: grid.bounds,
      fitBoundsOptions: { padding: 40 }, minZoom: 9, maxZoom: 17, attributionControl: { compact: true },
    })
    mapRef.current = map
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'bottom-right')

    map.on('load', () => {
      map.addSource('grid', { type: 'geojson', data: grid.geojson })
      map.addLayer({ id: 'grid-fill', type: 'fill', source: 'grid', paint: { 'fill-color': gridColor as never, 'fill-opacity': 0.5, 'fill-outline-color': 'rgba(0,0,0,0)' } })

      map.addSource('sel', { type: 'geojson', data: empty() })
      map.addLayer({ id: 'sel-line', type: 'line', source: 'sel', paint: { 'line-color': '#fff', 'line-width': 2.5 } })

      map.addSource('cand', { type: 'geojson', data: cands.geojson })
      map.addLayer({ id: 'cand', type: 'circle', source: 'cand', layout: { visibility: 'none' }, paint: {
        'circle-color': candColor as never, 'circle-radius': zoomR('pv', 250000, 700000, 1500000) as never,
        'circle-opacity': 0.85, 'circle-stroke-width': 0.5, 'circle-stroke-color': 'rgba(0,0,0,0.45)' } })

      map.addSource('ad', { type: 'geojson', data: stops.geojson })
      map.addLayer({ id: 'ad', type: 'circle', source: 'ad', layout: { visibility: 'none' }, paint: {
        'circle-color': valueColor as never, 'circle-radius': zoomR('r', 0, 3000, 8000) as never,
        'circle-opacity': 0.85, 'circle-stroke-width': 0.5, 'circle-stroke-color': 'rgba(0,0,0,0.45)' } })

      map.addSource('hi', { type: 'geojson', data: empty() })
      map.addLayer({ id: 'hi', type: 'circle', source: 'hi', paint: {
        'circle-color': 'rgba(0,0,0,0)', 'circle-radius': 9, 'circle-stroke-width': 2.5, 'circle-stroke-color': '#fff' } })

      ready.current = true
      apply(); syncHi()
    })

    map.on('click', (e) => {
      const t = ctRef.current
      if (t === 'grid') { cbRef.current.onPickGrid(e.lngLat.lat, e.lngLat.lng); return }
      const layer = t === 'ad' ? 'ad' : 'cand'
      const hit = map.queryRenderedFeatures(e.point, { layers: [layer] })
      if (hit.length) {
        const idx = hit[0].properties!.idx as number
        if (t === 'ad') cbRef.current.onPickAd(idx); else cbRef.current.onPickCand(idx)
      }
    })
    const hover = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 12, className: 'stop-pop' })
    const onMove = (layer: 'ad' | 'cand') => (e: maplibregl.MapLayerMouseEvent) => {
      map.getCanvas().style.cursor = 'pointer'
      const f = e.features?.[0]; if (!f) return
      const i = f.properties!.idx as number
      if (layer === 'ad') {
        const s = stops.stops[i]
        hover.setLngLat(e.lngLat).setHTML(`<b>${s.name}</b><span>${manWon(s.price)}원 · 일 ${(s.riders ?? 0).toLocaleString('ko-KR')}명</span>`).addTo(map)
      } else {
        const c = cands.list[i]
        hover.setLngLat(e.lngLat).setHTML(`<b>${c.name}</b><span>신설 시 약 ${manWon(c.predValue)}원/면</span>`).addTo(map)
      }
    }
    map.on('mousemove', 'ad', onMove('ad'))
    map.on('mousemove', 'cand', onMove('cand'))
    const leave = () => { map.getCanvas().style.cursor = ''; hover.remove() }
    map.on('mouseleave', 'ad', leave)
    map.on('mouseleave', 'cand', leave)

    return () => { map.remove(); mapRef.current = null; ready.current = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => { if (flyTo && mapRef.current) mapRef.current.flyTo({ center: flyTo, zoom: 14, speed: 1.2 }) }, [flyTo])

  function apply() {
    const map = mapRef.current
    if (!map || !ready.current) return
    const vis = (b: boolean) => (b ? 'visible' : 'none')
    map.setLayoutProperty('grid-fill', 'visibility', vis(heat.on))
    map.setPaintProperty('grid-fill', 'fill-opacity', heat.opacity)
    map.setLayoutProperty('cand', 'visibility', vis(pointLayer === 'cand'))
    const adOn = pointLayer === 'adValue' || pointLayer === 'adVerdict'
    map.setLayoutProperty('ad', 'visibility', vis(adOn))
    if (adOn) map.setPaintProperty('ad', 'circle-color', (pointLayer === 'adVerdict' ? verdictColor : valueColor) as never)
    map.setLayoutProperty('sel-line', 'visibility', vis(clickTarget === 'grid'))
  }
  useEffect(apply, [heat, pointLayer, clickTarget])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !ready.current) return
    ;(map.getSource('sel') as maplibregl.GeoJSONSource | undefined)?.setData(
      gridSel ? { type: 'FeatureCollection', features: [grid.geojson.features[gridSel.idx]] } : empty())
  }, [gridSel, grid])

  function syncHi() {
    const map = mapRef.current
    if (!map || !ready.current) return
    const feats: GeoJSON.Feature[] = []
    for (const i of basket) { const f = stops.geojson.features[i]; if (f) feats.push(f) }
    if (selectedAd != null && stops.geojson.features[selectedAd]) feats.push(stops.geojson.features[selectedAd])
    if (selectedCand != null && cands.geojson.features[selectedCand]) feats.push(cands.geojson.features[selectedCand])
    ;(map.getSource('hi') as maplibregl.GeoJSONSource | undefined)?.setData({ type: 'FeatureCollection', features: feats })

    markerRef.current?.remove(); markerRef.current = null
    let pt: { lng: number; lat: number; name: string; sub: string } | null = null
    if (selectedAd != null) { const s = stops.stops[selectedAd]; pt = { lng: s.lng, lat: s.lat, name: s.name, sub: `${manWon(s.price)}원` } }
    else if (selectedCand != null) { const c = cands.list[selectedCand]; pt = { lng: c.lng, lat: c.lat, name: c.name, sub: `신설 ${manWon(c.predValue)}원` } }
    if (pt) {
      const el = document.createElement('div')
      el.className = 'map-pin'; el.style.setProperty('--pin', '#4f6bff')
      el.innerHTML = `<span class="map-pin__tag">${pt.name}</span><span class="map-pin__price">${pt.sub}</span>`
      markerRef.current = new maplibregl.Marker({ element: el, anchor: 'bottom' }).setLngLat([pt.lng, pt.lat]).addTo(map)
    }
  }
  useEffect(syncHi, [selectedAd, selectedCand, basket, stops, cands])

  return <div ref={containerRef} className="map" />
}

function empty(): GeoJSON.FeatureCollection { return { type: 'FeatureCollection', features: [] } }
