import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { useEffect, useRef } from 'react'
import {
  AIR_GRADE_COLOR,
  BUSAN_BOUNDS,
  MAP_STYLE_URL,
  SATELLITE_ATTRIBUTION,
  SATELLITE_TILES,
  categoryMeta,
  weatherIcon,
  windColor,
} from '../../lib/constants'
import { circlePolygon } from '../../lib/geo'
import type { AirStation, DistrictWeather, IssueSummary, MapLayers, UserLocation } from '../../types'

interface IssueMapProps {
  issues: IssueSummary[]
  location: UserLocation
  radiusKm: number
  selectedId: number | null
  onSelect: (id: number) => void
  layers: MapLayers
  districtWeather: DistrictWeather[]
  airStations: AirStation[]
}

const RADIUS_SOURCE = 'search-radius'
const SATELLITE_LAYER = 'satellite'

/** 오버레이 마커 묶음을 데이터로 다시 그린다 (레이어가 꺼져 있으면 items를 빈 배열로) */
function syncMarkers<T>(
  map: maplibregl.Map,
  store: maplibregl.Marker[],
  items: T[],
  make: (item: T) => maplibregl.Marker,
): maplibregl.Marker[] {
  store.forEach((m) => m.remove())
  return items.map((item) => make(item).addTo(map))
}

function weatherElement(d: DistrictWeather): HTMLElement {
  const w = d.weather
  const el = document.createElement('div')
  el.className = 'weather-marker'
  el.textContent = `${weatherIcon(w.precipitation_type, w.sky)} ${w.temperature != null ? Math.round(w.temperature) + '°' : '-'}`
  el.title = `${d.district} · ${w.precipitation_type !== '없음' ? w.precipitation_type : (w.sky ?? '')} · 습도 ${w.humidity ?? '-'}%`
  return el
}

function windElement(d: DistrictWeather): HTMLElement {
  const { wind_direction: dir, wind_speed: speed } = d.weather
  const el = document.createElement('div')
  el.className = 'wind-marker'
  el.style.setProperty('--wind-color', windColor(speed))
  // 기상청 풍향은 '불어오는' 방향이라 180°를 더해 '불어 가는' 방향으로 화살표를 돌린다
  const rotation = dir != null ? dir + 180 : 0
  el.innerHTML = `<svg viewBox="0 0 24 24" width="18" height="18" style="transform: rotate(${rotation}deg)" aria-hidden="true"><path d="M12 2 L18 14 L13 12 L13 22 L11 22 L11 12 L6 14 Z" fill="currentColor"/></svg><span></span>`
  el.querySelector('span')!.textContent = speed != null ? `${speed}` : '-'
  el.title = `${d.district} 바람 ${speed ?? '-'}m/s (${dir ?? '-'}°에서 불어옴)`
  return el
}

function airElement(s: AirStation): HTMLElement {
  const el = document.createElement('div')
  el.className = 'air-marker'
  el.style.setProperty('--air-color', s.grade ? AIR_GRADE_COLOR[s.grade] : '#8b98a8')
  el.textContent = String(s.pm10 ?? s.pm25 ?? '-')
  el.title = `${s.station} 측정소 · PM10 ${s.pm10 ?? '-'}㎍/㎥ (${s.pm10_grade ?? '-'}) · PM2.5 ${s.pm25 ?? '-'}㎍/㎥ (${s.pm25_grade ?? '-'})`
  return el
}

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

export default function IssueMap({
  issues,
  location,
  radiusKm,
  selectedId,
  onSelect,
  layers,
  districtWeather,
  airStations,
}: IssueMapProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<maplibregl.Map | null>(null)
  const markersRef = useRef(new Map<number, maplibregl.Marker>())
  const locationMarkerRef = useRef<maplibregl.Marker | null>(null)
  const onSelectRef = useRef(onSelect)
  const overlayRef = useRef({ weather: [] as maplibregl.Marker[], wind: [] as maplibregl.Marker[], air: [] as maplibregl.Marker[] })
  // 스타일이 로드될 때 위성사진 표시 여부를 정하기 위해 최신 값을 둔다
  const satelliteRef = useRef(layers.satellite)
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
      // CARTO 스타일의 영문 지명(name_en, name:en)을 현지어(한국어) 지명으로 바꾼다
      for (const layer of map.getStyle().layers) {
        if (layer.type !== 'symbol') continue
        const field = JSON.stringify(map.getLayoutProperty(layer.id, 'text-field') ?? '')
        if (field.includes('name_en') || field.includes('name:en')) {
          map.setLayoutProperty(layer.id, 'text-field', ['coalesce', ['get', 'name'], ['get', 'name_en']])
        }
      }
      // 위성사진: 지명(symbol) 레이어 아래에 넣어 지명은 위성사진 위에 그대로 보이게 한다
      const firstSymbol = map.getStyle().layers.find((l) => l.type === 'symbol')?.id
      map.addSource(SATELLITE_LAYER, {
        type: 'raster',
        tiles: [SATELLITE_TILES],
        tileSize: 256,
        maxzoom: 15,
        attribution: SATELLITE_ATTRIBUTION,
      })
      map.addLayer(
        {
          id: SATELLITE_LAYER,
          type: 'raster',
          source: SATELLITE_LAYER,
          layout: { visibility: satelliteRef.current ? 'visible' : 'none' },
        },
        firstSymbol,
      )

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
    const overlays = overlayRef.current
    return () => {
      markers.clear()
      overlays.weather = []
      overlays.wind = []
      overlays.air = []
      map.remove()
      mapRef.current = null
    }
  }, [])

  // 위성사진 켜기/끄기 (스타일 로드 전이면 style.load 핸들러가 satelliteRef 값으로 정한다)
  useEffect(() => {
    satelliteRef.current = layers.satellite
    const map = mapRef.current
    if (map?.getLayer(SATELLITE_LAYER)) {
      map.setLayoutProperty(SATELLITE_LAYER, 'visibility', layers.satellite ? 'visible' : 'none')
    }
  }, [layers.satellite])

  // 날씨 레이어: 구·군마다 하늘 아이콘과 기온
  useEffect(() => {
    const map = mapRef.current
    if (!map) return
    overlayRef.current.weather = syncMarkers(map, overlayRef.current.weather, layers.weather ? districtWeather : [], (d) =>
      new maplibregl.Marker({ element: weatherElement(d), offset: [0, -14] }).setLngLat([d.lng, d.lat]),
    )
  }, [layers.weather, districtWeather])

  // 바람 레이어: 구·군마다 불어 가는 방향의 화살표와 풍속 (날씨 마커 아래쪽에 둔다)
  useEffect(() => {
    const map = mapRef.current
    if (!map) return
    overlayRef.current.wind = syncMarkers(map, overlayRef.current.wind, layers.wind ? districtWeather : [], (d) =>
      new maplibregl.Marker({ element: windElement(d), offset: [0, 14] }).setLngLat([d.lng, d.lat]),
    )
  }, [layers.wind, districtWeather])

  // 미세먼지 레이어: 측정소마다 등급 색과 PM10 수치
  useEffect(() => {
    const map = mapRef.current
    if (!map) return
    overlayRef.current.air = syncMarkers(map, overlayRef.current.air, layers.air ? airStations : [], (s) =>
      new maplibregl.Marker({ element: airElement(s) }).setLngLat([s.lng, s.lat]),
    )
  }, [layers.air, airStations])

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

  // 이슈 마커 다시 그리기 (뉴스 이슈 레이어를 끄면 지운다)
  useEffect(() => {
    const map = mapRef.current
    if (!map) return
    const markers = markersRef.current
    markers.forEach((m) => m.remove())
    markers.clear()
    if (!layers.issues) return
    for (const issue of issues) {
      if (issue.lat == null || issue.lng == null) continue
      const el = createMarkerElement(issue, () => onSelectRef.current(issue.id))
      markers.set(issue.id, new maplibregl.Marker({ element: el }).setLngLat([issue.lng, issue.lat]).addTo(map))
    }
  }, [issues, layers.issues])

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
