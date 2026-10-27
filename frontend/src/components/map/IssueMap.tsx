import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import type { FeatureCollection } from 'geojson'
import { useEffect, useMemo, useRef } from 'react'
import {
  AIR_GRADE_COLOR,
  BUSAN_BOUNDS,
  BUSAN_LAND_BOUNDS,
  MAP_STYLE_URL,
  SATELLITE_ATTRIBUTION,
  SATELLITE_TILES,
  categoryMeta,
} from '../../lib/constants'
import { circlePolygon } from '../../lib/geo'
import { fillGrid, renderTemperatureImage, windDirectionName } from '../../lib/weatherField'
import type { AirStation, IssueSummary, MapLayers, UserLocation, WeatherGrid, WeatherNow } from '../../types'
import { startWindParticles } from './windParticles'

interface IssueMapProps {
  issues: IssueSummary[]
  location: UserLocation
  radiusKm: number
  selectedId: number | null
  onSelect: (id: number) => void
  layers: MapLayers
  weatherGrid: WeatherGrid | null
  airStations: AirStation[]
  /** 기준 위치의 현재 날씨 (기온·바람 레이어를 켜면 말풍선으로 보여준다) */
  weather: WeatherNow | null
}

const RADIUS_SOURCE = 'search-radius'
const SATELLITE_LAYER = 'satellite'
const TEMPERATURE_LAYER = 'temperature'
const EMPTY: FeatureCollection = { type: 'FeatureCollection', features: [] }

/** 이미지 소스 좌표: 지도 이동 범위 전체 (좌상, 우상, 우하, 좌하) */
const [[WEST, SOUTH], [EAST, NORTH]] = BUSAN_BOUNDS
const IMAGE_CORNERS: [[number, number], [number, number], [number, number], [number, number]] = [
  [WEST, NORTH],
  [EAST, NORTH],
  [EAST, SOUTH],
  [WEST, SOUTH],
]

function createMarkerElement(issue: IssueSummary, onClick: () => void): HTMLElement {
  const el = document.createElement('button')
  el.type = 'button'
  el.className = `issue-marker${issue.importance === 'high' ? ' issue-marker--pulse' : ''}`
  const meta = categoryMeta(issue.category)
  el.style.setProperty('--marker-color', meta.color)
  // 위치(transform)는 바깥 요소에 MapLibre가 주고, 모양과 확대 효과는 안쪽 요소가 맡는다
  const dot = document.createElement('span')
  dot.className = 'issue-marker__dot'
  dot.textContent = meta.icon
  el.append(dot)
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

function airElement(s: AirStation): HTMLElement {
  const el = document.createElement('div')
  el.className = 'air-marker'
  el.style.setProperty('--air-color', s.grade ? AIR_GRADE_COLOR[s.grade] : '#8b98a8')
  el.textContent = String(s.pm10 ?? s.pm25 ?? '-')
  el.title = `${s.station} 측정소 · PM10 ${s.pm10 ?? '-'}㎍/㎥ (${s.pm10_grade ?? '-'}) · PM2.5 ${s.pm25 ?? '-'}㎍/㎥ (${s.pm25_grade ?? '-'})`
  return el
}

/** 기준 위치 말풍선: 애플 날씨처럼 기온 또는 바람을 크게 보여준다 */
function bubbleElement(weather: WeatherNow, mode: 'temperature' | 'wind'): HTMLElement {
  const el = document.createElement('div')
  el.className = 'weather-bubble'
  const main = document.createElement('strong')
  const sub = document.createElement('span')
  if (mode === 'wind') {
    const dir = weather.wind_direction != null ? windDirectionName(weather.wind_direction) : ''
    main.textContent = weather.wind_speed != null ? `${weather.wind_speed}` : '-'
    sub.textContent = `${dir} m/s`
  } else {
    main.textContent = weather.temperature != null ? `${Math.round(weather.temperature)}°` : '-'
    sub.textContent = weather.precipitation_type !== '없음' ? weather.precipitation_type : (weather.sky ?? '')
  }
  el.append(main, sub)
  return el
}

export default function IssueMap({
  issues,
  location,
  radiusKm,
  selectedId,
  onSelect,
  layers,
  weatherGrid,
  airStations,
  weather,
}: IssueMapProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const windCanvasRef = useRef<HTMLCanvasElement>(null)
  const mapRef = useRef<maplibregl.Map | null>(null)
  const markersRef = useRef(new Map<number, maplibregl.Marker>())
  const airMarkersRef = useRef<maplibregl.Marker[]>([])
  const locationMarkerRef = useRef<maplibregl.Marker | null>(null)
  const bubbleRef = useRef<maplibregl.Marker | null>(null)
  const onSelectRef = useRef(onSelect)
  // 최신 위치·반경과 레이어. 지도 생성과 스타일 로드 시점에 이 값을 쓴다.
  const viewRef = useRef({ location, radiusKm })
  const satelliteRef = useRef(layers.satellite)
  useEffect(() => {
    onSelectRef.current = onSelect
  }, [onSelect])

  // 바다처럼 관측이 없는 칸을 채운 격자 (기온 면과 바람 입자가 같이 쓴다)
  const filled = useMemo(() => (weatherGrid ? fillGrid(weatherGrid) : null), [weatherGrid])
  const temperatureImage = useMemo(() => (filled ? renderTemperatureImage(filled, BUSAN_BOUNDS) : null), [filled])
  const temperatureRef = useRef<{ on: boolean; image: string | null }>({ on: layers.weather, image: temperatureImage })

  // 지도 생성 (한 번)
  useEffect(() => {
    if (!containerRef.current) return
    const start = viewRef.current.location
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: MAP_STYLE_URL,
      center: [start.lng, start.lat],
      zoom: 11,
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
      // 위성사진·기온 면은 땅·물 면 바로 위, 도로·지명 아래에 넣어 도로와 지명이 위에 보이게 한다
      const firstSymbol = belowRoads(map)
      map.addSource(SATELLITE_LAYER, {
        type: 'raster',
        tiles: [SATELLITE_TILES],
        tileSize: 256,
        maxzoom: 15,
        attribution: SATELLITE_ATTRIBUTION,
      })
      map.addLayer(
        { id: SATELLITE_LAYER, type: 'raster', source: SATELLITE_LAYER, layout: { visibility: satelliteRef.current ? 'visible' : 'none' } },
        firstSymbol,
      )
      const { on, image } = temperatureRef.current
      if (image) addTemperatureLayer(map, image, on, firstSymbol)

      // 스타일을 받는 사이에 위치가 바뀌었을 수 있어 최신 값으로 그린다
      const { location: loc, radiusKm: r } = viewRef.current
      map.addSource(RADIUS_SOURCE, { type: 'geojson', data: loc.wholeCity ? EMPTY : circlePolygon(loc.lat, loc.lng, r) })
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
      airMarkersRef.current = []
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

  // 기온 면: 격자를 색으로 칠한 이미지를 지도 전체에 깐다
  useEffect(() => {
    temperatureRef.current = { on: layers.weather, image: temperatureImage }
    const map = mapRef.current
    if (!map || !temperatureImage) return
    const source = map.getSource<maplibregl.ImageSource>(TEMPERATURE_LAYER)
    if (source) {
      source.updateImage({ url: temperatureImage, coordinates: IMAGE_CORNERS })
      map.setLayoutProperty(TEMPERATURE_LAYER, 'visibility', layers.weather ? 'visible' : 'none')
    } else if (map.getSource(RADIUS_SOURCE)) {
      // 스타일이 이미 로드된 뒤 처음 데이터가 온 경우 (로드 전이면 style.load 핸들러가 추가한다)
      addTemperatureLayer(map, temperatureImage, layers.weather, belowRoads(map))
    }
  }, [layers.weather, temperatureImage])

  // 바람 입자: 켜져 있는 동안 캔버스에서 계속 흘려 보낸다
  useEffect(() => {
    const map = mapRef.current
    const canvas = windCanvasRef.current
    if (!map || !canvas || !layers.wind || !filled) return
    return startWindParticles(map, canvas, filled)
  }, [layers.wind, filled])

  // 미세먼지 레이어: 측정소마다 등급 색과 PM10 수치
  useEffect(() => {
    const map = mapRef.current
    if (!map) return
    airMarkersRef.current.forEach((m) => m.remove())
    airMarkersRef.current = (layers.air ? airStations : []).map((s) =>
      new maplibregl.Marker({ element: airElement(s) }).setLngLat([s.lng, s.lat]).addTo(map),
    )
  }, [layers.air, airStations])

  // 기준 위치 말풍선 (기온 또는 바람 레이어가 켜져 있을 때, 부산 전체 보기에서는 숨김)
  useEffect(() => {
    const map = mapRef.current
    bubbleRef.current?.remove()
    bubbleRef.current = null
    if (!map || !weather || location.wholeCity || !(layers.weather || layers.wind)) return
    const mode = layers.wind && !layers.weather ? 'wind' : 'temperature'
    bubbleRef.current = new maplibregl.Marker({ element: bubbleElement(weather, mode), anchor: 'bottom', offset: [0, -12] })
      .setLngLat([location.lng, location.lat])
      .addTo(map)
  }, [weather, location, layers.weather, layers.wind])

  // 기준 위치·반경이 바뀌면 위치 표시와 반경 원을 갱신하고 이동
  useEffect(() => {
    viewRef.current = { location, radiusKm }
    const map = mapRef.current
    if (!map) return
    const radius = map.getSource<maplibregl.GeoJSONSource>(RADIUS_SOURCE)

    if (location.wholeCity) {
      // 부산 전체: 반경 원과 위치 점 없이 부산 전역이 보이게
      locationMarkerRef.current?.remove()
      radius?.setData(EMPTY)
      map.fitBounds(BUSAN_LAND_BOUNDS, { padding: 20, speed: 1.4 })
      return
    }
    if (!locationMarkerRef.current) {
      locationMarkerRef.current = new maplibregl.Marker({ element: createLocationElement() })
    }
    locationMarkerRef.current.setLngLat([location.lng, location.lat]).addTo(map)

    // 반경 원이 아직 없으면(스타일 로드 전) style.load 핸들러가 viewRef의 최신 값으로 그린다.
    // isStyleLoaded()는 타일을 받는 중에도 false라서 판단 기준으로 쓰지 않는다.
    radius?.setData(circlePolygon(location.lat, location.lng, radiusKm))

    // 반경 원이 화면에 들어오도록 확대 수준을 맞춘다
    const zoom = radiusKm <= 2 ? 13 : radiusKm <= 5 ? 12 : radiusKm <= 10 ? 11 : 10
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

  return (
    <div className="relative h-full w-full">
      <div ref={containerRef} className="h-full w-full" />
      {/* 바람 입자 캔버스: 지도 위에 겹치되 마우스 조작은 지도로 넘긴다 */}
      <canvas ref={windCanvasRef} className="pointer-events-none absolute inset-0" aria-hidden />
    </div>
  )
}

function addTemperatureLayer(map: maplibregl.Map, image: string, visible: boolean, beforeId: string | undefined) {
  map.addSource(TEMPERATURE_LAYER, { type: 'image', url: image, coordinates: IMAGE_CORNERS })
  map.addLayer(
    {
      id: TEMPERATURE_LAYER,
      type: 'raster',
      source: TEMPERATURE_LAYER,
      layout: { visibility: visible ? 'visible' : 'none' },
      paint: { 'raster-opacity': 0.75, 'raster-resampling': 'linear', 'raster-fade-duration': 0 },
    },
    beforeId,
  )
}

/** 땅·물 면(fill) 다음에 오는 첫 레이어 id. 그 앞에 넣으면 도로(line)·지명(symbol)보다 아래에 깔린다 */
function belowRoads(map: maplibregl.Map): string | undefined {
  const layers = map.getStyle().layers
  const lastFill = layers.reduce((last, layer, i) => (layer.type === 'fill' && layer.id.startsWith('water') ? i : last), -1)
  // 이미 넣은 위성사진·기온 면은 건너뛴다 → 나중에 넣는 기온 면이 위성사진 위에 온다
  const next = layers.slice(lastFill + 1).find((l) => l.id !== SATELLITE_LAYER && l.id !== TEMPERATURE_LAYER)?.id
  return lastFill >= 0 && next ? next : layers.find((l) => l.type === 'symbol')?.id
}
