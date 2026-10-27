import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { useEffect, useRef } from 'react'
import { BUSAN_BOUNDS, MAP_STYLE_URL, categoryMeta } from '../../lib/constants'
import { circlePolygon } from '../../lib/geo'
import type { IssueSummary, UserLocation } from '../../types'

interface IssueMapProps {
  issues: IssueSummary[]
  location: UserLocation
  radiusKm: number
  selectedId: number | null
  onSelect: (id: number) => void
}

const RADIUS_SOURCE = 'search-radius'

function createMarkerElement(issue: IssueSummary, onClick: () => void): HTMLElement {
  const el = document.createElement('button')
  el.type = 'button'
  el.className = `issue-marker${issue.importance === 'high' ? ' issue-marker--pulse' : ''}`
  const meta = categoryMeta(issue.category)
  el.style.setProperty('--marker-color', meta.color)
  el.textContent = meta.icon
  el.title = issue.title
  el.setAttribute('aria-label', issue.title)
  el.addEventListener('click', (e) => {
    e.stopPropagation()
    onClick()
  })
  return el
}

function createLocationElement(): HTMLElement {
  const el = document.createElement('div')
  el.className = 'user-location'
  el.setAttribute('aria-label', '기준 위치')
  return el
}

export default function IssueMap({ issues, location, radiusKm, selectedId, onSelect }: IssueMapProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<maplibregl.Map | null>(null)
  const markersRef = useRef(new Map<number, maplibregl.Marker>())
  const locationMarkerRef = useRef<maplibregl.Marker | null>(null)
  const onSelectRef = useRef(onSelect)
  // 최신 위치·반경. 지도 생성과 스타일 로드 시점에 이 값을 쓴다.
  const viewRef = useRef({ location, radiusKm })
  useEffect(() => {
    onSelectRef.current = onSelect
  }, [onSelect])

  // 지도 생성 (한 번)
  useEffect(() => {
    if (!containerRef.current) return
    const start = viewRef.current.location
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: MAP_STYLE_URL,
      center: [start.lng, start.lat],
      zoom: 13,
      maxBounds: BUSAN_BOUNDS,
      attributionControl: { compact: true },
    })
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-left')
    map.on('style.load', () => {
      // CARTO 스타일의 영문 지명(name_en)을 현지어(한국어) 지명으로 바꾼다
      for (const layer of map.getStyle().layers) {
        if (layer.type !== 'symbol') continue
        const field = map.getLayoutProperty(layer.id, 'text-field')
        if (field && JSON.stringify(field).includes('name_en')) {
          map.setLayoutProperty(layer.id, 'text-field', ['coalesce', ['get', 'name'], ['get', 'name_en']])
        }
      }
      // 스타일을 받는 사이에 위치가 바뀌었을 수 있어 최신 값으로 그린다
      const { location: loc, radiusKm: r } = viewRef.current
      map.addSource(RADIUS_SOURCE, { type: 'geojson', data: circlePolygon(loc.lat, loc.lng, r) })
      map.addLayer({ id: 'radius-fill', type: 'fill', source: RADIUS_SOURCE, paint: { 'fill-color': '#38bdf8', 'fill-opacity': 0.06 } })
      map.addLayer({
        id: 'radius-line',
        type: 'line',
        source: RADIUS_SOURCE,
        paint: { 'line-color': '#38bdf8', 'line-opacity': 0.5, 'line-dasharray': [2, 2] },
      })
    })
    mapRef.current = map
    const markers = markersRef.current
    return () => {
      markers.clear()
      map.remove()
      mapRef.current = null
    }
  }, [])

  // 기준 위치·반경이 바뀌면 위치 표시와 반경 원을 갱신하고 이동
  useEffect(() => {
    viewRef.current = { location, radiusKm }
    const map = mapRef.current
    if (!map) return
    if (!locationMarkerRef.current) {
      locationMarkerRef.current = new maplibregl.Marker({ element: createLocationElement() })
    }
    locationMarkerRef.current.setLngLat([location.lng, location.lat]).addTo(map)

    // 반경 원이 아직 없으면(스타일 로드 전) style.load 핸들러가 viewRef의 최신 값으로 그린다.
    // isStyleLoaded()는 타일을 받는 중에도 false라서 판단 기준으로 쓰지 않는다.
    map.getSource<maplibregl.GeoJSONSource>(RADIUS_SOURCE)?.setData(circlePolygon(location.lat, location.lng, radiusKm))

    // 반경 원이 화면에 들어오도록 확대 수준을 맞춘다
    const zoom = radiusKm <= 2 ? 13 : radiusKm <= 5 ? 12 : 11
    map.flyTo({ center: [location.lng, location.lat], zoom, speed: 1.4 })
  }, [location, radiusKm])

  // 이슈 마커 다시 그리기
  useEffect(() => {
    const map = mapRef.current
    if (!map) return
    const markers = markersRef.current
    markers.forEach((m) => m.remove())
    markers.clear()
    for (const issue of issues) {
      if (issue.lat == null || issue.lng == null) continue
      const el = createMarkerElement(issue, () => onSelectRef.current(issue.id))
      markers.set(issue.id, new maplibregl.Marker({ element: el }).setLngLat([issue.lng, issue.lat]).addTo(map))
    }
  }, [issues])

  // 선택된 이슈 강조 + 이동
  useEffect(() => {
    const map = mapRef.current
    markersRef.current.forEach((marker, id) => {
      marker.getElement().classList.toggle('issue-marker--selected', id === selectedId)
    })
    if (!map || selectedId == null) return
    const issue = issues.find((i) => i.id === selectedId)
    if (issue?.lat == null || issue.lng == null) return
    map.flyTo({ center: [issue.lng, issue.lat], zoom: Math.max(map.getZoom(), 14), speed: 1.4 })
  }, [selectedId, issues])

  return <div ref={containerRef} className="h-full w-full" />
}
