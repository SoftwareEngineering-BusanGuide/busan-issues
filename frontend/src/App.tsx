import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  fetchAir,
  fetchAirStations,
  fetchAlerts,
  fetchIssueDetail,
  fetchNearbyIssues,
  fetchTopIssues,
  fetchWeather,
  fetchWeatherGrid,
} from './api/client'
import TopBar from './components/header/TopBar'
import TopIssues from './components/header/TopIssues'
import IssueMap from './components/map/IssueMap'
import LayerControl from './components/map/LayerControl'
import IssueDetailView from './components/panel/IssueDetailView'
import IssueList from './components/panel/IssueList'
import LocationControl from './components/panel/LocationControl'
import AlertTicker from './components/ticker/AlertTicker'
import {
  DEFAULT_LAYERS,
  DEFAULT_LOCATION,
  DEFAULT_PERIOD_DAYS,
  DEFAULT_RADIUS_KM,
  DISTRICTS,
  WHOLE_CITY_LABEL,
  WHOLE_CITY_LOCATION,
  WHOLE_CITY_RADIUS_KM,
} from './lib/constants'
import { isInBusan } from './lib/geo'
import type {
  AirNow,
  AirStation,
  Alert,
  IssueDetail,
  IssueSummary,
  MapLayers,
  NearbyIssue,
  UserLocation,
  WeatherGrid,
  WeatherNow,
} from './types'

const SERVER_ERROR = '서버에 연결할 수 없습니다. 백엔드가 실행 중인지 확인하세요.'
const REFRESH_MS = 60_000
const GEO_SUPPORTED = 'geolocation' in navigator
const GEO_UNSUPPORTED_NOTICE = '이 브라우저는 위치 기능을 지원하지 않습니다. 구·군을 직접 선택하세요.'

const LAYERS_STORAGE_KEY = 'busan-alimi:layers'

/** 사용자가 고른 지도 레이어를 브라우저에 기억한다. 저장소를 못 쓰면 기본값 */
function loadLayers(): MapLayers {
  try {
    const saved = JSON.parse(localStorage.getItem(LAYERS_STORAGE_KEY) ?? 'null') as Partial<MapLayers> | null
    return { ...DEFAULT_LAYERS, ...(saved ?? {}) }
  } catch {
    return DEFAULT_LAYERS
  }
}

function saveLayers(layers: MapLayers): void {
  try {
    localStorage.setItem(LAYERS_STORAGE_KEY, JSON.stringify(layers))
  } catch {
    // 시크릿 모드 등 저장소를 못 쓰면 이번 방문 동안만 유지한다
  }
}

interface NearbyResult {
  /** 어떤 조건(위치·반경·분류)으로 받은 결과인지. 지금 조건과 다르면 불러오는 중이다. */
  key: string
  data: NearbyIssue[]
  error: string | null
}

interface DetailResult {
  id: number
  data: IssueDetail | null
  error: string | null
}

export default function App() {
  const [now, setNow] = useState(() => Date.now())
  const [location, setLocation] = useState<UserLocation>(DEFAULT_LOCATION)
  const [radiusKm, setRadiusKm] = useState(DEFAULT_RADIUS_KM)
  const [category, setCategory] = useState('')
  const [periodDays, setPeriodDays] = useState(DEFAULT_PERIOD_DAYS)
  // 접속하자마자 위치를 요청하므로 처음부터 '확인 중' 상태로 시작한다
  const [locating, setLocating] = useState(GEO_SUPPORTED)
  const [notice, setNotice] = useState<string | null>(GEO_SUPPORTED ? null : GEO_UNSUPPORTED_NOTICE)

  const [nearbyResult, setNearbyResult] = useState<NearbyResult>({ key: '', data: [], error: null })
  const [topIssues, setTopIssues] = useState<IssueSummary[]>([])
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [alertsError, setAlertsError] = useState(false)
  const [weather, setWeather] = useState<WeatherNow | null>(null)
  const [air, setAir] = useState<AirNow | null>(null)

  // 지도 레이어
  const [layers, setLayers] = useState<MapLayers>(loadLayers)
  const [weatherGrid, setWeatherGrid] = useState<WeatherGrid | null>(null)
  const [airStations, setAirStations] = useState<AirStation[]>([])
  const [layerErrors, setLayerErrors] = useState<Partial<Record<keyof MapLayers, boolean>>>({})
  const toggleLayer = (key: keyof MapLayers) =>
    setLayers((prev) => {
      const next = { ...prev, [key]: !prev[key] }
      saveLayers(next)
      return next
    })

  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [detailResult, setDetailResult] = useState<DetailResult | null>(null)

  // 1분마다 시각을 갱신하고, 그때 목록도 다시 불러온다
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), REFRESH_MS)
    return () => clearInterval(timer)
  }, [])

  // FR-001 / UC-001: 위치 권한을 요청하고, 거부하거나 부산 밖이면 기본 위치를 쓴다
  const requestPosition = useCallback(() => {
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => {
        setLocating(false)
        if (isInBusan(coords.latitude, coords.longitude)) {
          setLocation({ lat: coords.latitude, lng: coords.longitude, label: '현재 위치' })
          setNotice(null)
        } else {
          setLocation(DEFAULT_LOCATION)
          setNotice('현재 위치가 부산 밖이라 기본 위치(부산시청)를 보여줍니다.')
        }
      },
      () => {
        setLocating(false)
        setNotice('위치 권한이 없어 기본 위치(부산시청)를 보여줍니다. 구·군을 직접 선택할 수 있습니다.')
      },
      { timeout: 8000, maximumAge: 60_000 },
    )
  }, [])

  useEffect(() => {
    if (GEO_SUPPORTED) requestPosition()
  }, [requestPosition])

  const locate = () => {
    if (!GEO_SUPPORTED) {
      setNotice(GEO_UNSUPPORTED_NOTICE)
      return
    }
    setLocating(true)
    requestPosition()
  }

  const selectDistrict = (name: string) => {
    if (name === WHOLE_CITY_LABEL) {
      setLocation(WHOLE_CITY_LOCATION)
      setNotice(null)
      return
    }
    const d = DISTRICTS.find((x) => x.name === name)
    if (!d) return
    setLocation({ lat: d.lat, lng: d.lng, label: d.name })
    setNotice(null)
  }

  // API-002 내 주변 이슈 ('부산 전체'면 반경 대신 부산 전역)
  const searchRadius = location.wholeCity ? WHOLE_CITY_RADIUS_KM : radiusKm
  const nearbyKey = `${location.lat},${location.lng},${searchRadius},${periodDays},${category}`
  useEffect(() => {
    let ignore = false
    fetchNearbyIssues(location.lat, location.lng, searchRadius, periodDays, category || undefined)
      .then((data) => !ignore && setNearbyResult({ key: nearbyKey, data, error: null }))
      .catch(() => !ignore && setNearbyResult({ key: nearbyKey, data: [], error: SERVER_ERROR }))
    return () => {
      ignore = true
    }
  }, [nearbyKey, location.lat, location.lng, searchRadius, periodDays, category, now])
  const nearby = nearbyResult.data
  const nearbyLoading = nearbyResult.key !== nearbyKey

  // API-003 부산 주요 이슈 (선택한 기간 안)
  useEffect(() => {
    let ignore = false
    fetchTopIssues(periodDays)
      .then((data) => !ignore && setTopIssues(data))
      .catch(() => {})
    return () => {
      ignore = true
    }
  }, [periodDays, now])

  // API-007 재난문자
  useEffect(() => {
    let ignore = false
    fetchAlerts()
      .then((data) => {
        if (ignore) return
        setAlerts(data)
        setAlertsError(false)
      })
      .catch(() => !ignore && setAlertsError(true))
    return () => {
      ignore = true
    }
  }, [now])

  // 기온·바람 레이어 데이터: 부산 격자 실황 (둘 중 하나라도 켜져 있을 때만, 서버는 매시 한 번 갱신)
  const needWeatherGrid = layers.weather || layers.wind
  useEffect(() => {
    if (!needWeatherGrid) return
    let ignore = false
    fetchWeatherGrid()
      .then((data) => {
        if (ignore) return
        setWeatherGrid(data)
        setLayerErrors((e) => ({ ...e, weather: false, wind: false }))
      })
      .catch(() => !ignore && setLayerErrors((e) => ({ ...e, weather: true, wind: true })))
    return () => {
      ignore = true
    }
  }, [needWeatherGrid, now])

  // 미세먼지 레이어 데이터
  useEffect(() => {
    if (!layers.air) return
    let ignore = false
    fetchAirStations()
      .then((data) => {
        if (ignore) return
        setAirStations(data)
        setLayerErrors((e) => ({ ...e, air: false }))
      })
      .catch(() => !ignore && setLayerErrors((e) => ({ ...e, air: true })))
    return () => {
      ignore = true
    }
  }, [layers.air, now])

  // 기준 위치의 날씨·미세먼지 (서버가 10분 캐시하므로 1분마다 불러도 외부 API 호출은 늘지 않는다)
  useEffect(() => {
    let ignore = false
    fetchWeather(location.lat, location.lng)
      .then((data) => !ignore && setWeather(data))
      .catch(() => !ignore && setWeather(null))
    fetchAir(location.lat, location.lng)
      .then((data) => !ignore && setAir(data))
      .catch(() => !ignore && setAir(null))
    return () => {
      ignore = true
    }
  }, [location.lat, location.lng, now])

  // API-004 이슈 상세
  useEffect(() => {
    if (selectedId == null) return
    let ignore = false
    fetchIssueDetail(selectedId)
      .then((data) => !ignore && setDetailResult({ id: selectedId, data, error: null }))
      .catch(() => !ignore && setDetailResult({ id: selectedId, data: null, error: '이슈를 불러오지 못했습니다.' }))
    return () => {
      ignore = true
    }
  }, [selectedId])
  // 다른 이슈를 고르면 새 응답이 올 때까지 이전 상세 대신 '불러오는 중'을 보여준다
  const current = detailResult?.id === selectedId ? detailResult : null
  const detail = current?.data ?? null
  const detailError = current?.error ?? null

  // 지도에는 주변 이슈와 함께, 반경 밖의 주요 이슈를 골랐다면 그 이슈도 표시한다
  const mapIssues = useMemo(() => {
    if (selectedId == null || nearby.some((i) => i.id === selectedId)) return nearby
    const selected = topIssues.find((i) => i.id === selectedId) ?? (detail?.issue.id === selectedId ? detail.issue : undefined)
    return selected ? [...nearby, selected] : nearby
  }, [nearby, topIssues, detail, selectedId])

  return (
    <div className="flex h-dvh flex-col">
      <TopBar now={now} weather={weather} air={air} />
      <TopIssues issues={topIssues} now={now} selectedId={selectedId} onSelect={setSelectedId} />

      <main className="flex min-h-0 flex-1 flex-col md:flex-row">
        <div className="relative h-[45dvh] shrink-0 md:h-auto md:flex-1">
          <IssueMap
            issues={mapIssues}
            location={location}
            radiusKm={radiusKm}
            selectedId={selectedId}
            onSelect={setSelectedId}
            layers={layers}
            weatherGrid={weatherGrid}
            weather={weather}
            airStations={airStations}
          />
          <LayerControl
            layers={layers}
            onToggle={toggleLayer}
            unavailable={layerErrors}
            observedAt={weatherGrid?.observed_at ?? null}
          />
          {notice && (
            <div className="absolute top-14 right-3 left-14 z-10 flex items-start md:top-3 md:right-auto md:left-1/2 md:w-[400px] md:-translate-x-1/2 gap-2 rounded-lg border border-caution/40 bg-panel/95 px-3 py-2 text-xs shadow-lg">
              <span className="flex-1">{notice}</span>
              <button type="button" onClick={() => setNotice(null)} aria-label="안내 닫기" className="text-muted hover:text-foreground">
                ✕
              </button>
            </div>
          )}
        </div>

        <aside className="flex min-h-0 flex-1 flex-col border-t border-line bg-panel md:w-[380px] md:flex-none md:border-t-0 md:border-l">
          <LocationControl
            location={location}
            radiusKm={radiusKm}
            periodDays={periodDays}
            locating={locating}
            onUseMyLocation={locate}
            onSelectDistrict={selectDistrict}
            onRadiusChange={setRadiusKm}
            onPeriodChange={setPeriodDays}
          />
          {selectedId == null ? (
            <IssueList
              issues={nearby}
              now={now}
              loading={nearbyLoading}
              error={nearbyResult.error}
              category={category}
              onCategoryChange={setCategory}
              onSelect={setSelectedId}
              showDistance={!location.wholeCity}
            />
          ) : (
            <IssueDetailView detail={detail} error={detailError} now={now} onBack={() => setSelectedId(null)} />
          )}
          <p className="shrink-0 border-t border-line px-4 py-2 text-[10px] leading-relaxed text-muted">
            공식 재난 알림(긴급재난문자)을 대체하지 않는 보조 정보 서비스입니다. 기사는 제목·요약과 원문 링크만 제공합니다.
          </p>
        </aside>
      </main>

      <AlertTicker alerts={alerts} error={alertsError} now={now} />
    </div>
  )
}
