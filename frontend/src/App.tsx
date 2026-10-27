import { useCallback, useEffect, useMemo, useState } from 'react'
import { fetchAir, fetchAlerts, fetchIssueDetail, fetchNearbyIssues, fetchTopIssues, fetchWeather } from './api/client'
import TopBar from './components/header/TopBar'
import TopIssues from './components/header/TopIssues'
import IssueMap from './components/map/IssueMap'
import IssueDetailView from './components/panel/IssueDetailView'
import IssueList from './components/panel/IssueList'
import LocationControl from './components/panel/LocationControl'
import AlertTicker from './components/ticker/AlertTicker'
import { DEFAULT_LOCATION, DISTRICTS, RADIUS_OPTIONS_KM } from './lib/constants'
import { isInBusan } from './lib/geo'
import type { AirNow, Alert, IssueDetail, IssueSummary, NearbyIssue, UserLocation, WeatherNow } from './types'

const SERVER_ERROR = '서버에 연결할 수 없습니다. 백엔드가 실행 중인지 확인하세요.'
const REFRESH_MS = 60_000
const GEO_SUPPORTED = 'geolocation' in navigator
const GEO_UNSUPPORTED_NOTICE = '이 브라우저는 위치 기능을 지원하지 않습니다. 구·군을 직접 선택하세요.'

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
  const [radiusKm, setRadiusKm] = useState(RADIUS_OPTIONS_KM[0])
  const [category, setCategory] = useState('')
  // 접속하자마자 위치를 요청하므로 처음부터 '확인 중' 상태로 시작한다
  const [locating, setLocating] = useState(GEO_SUPPORTED)
  const [notice, setNotice] = useState<string | null>(GEO_SUPPORTED ? null : GEO_UNSUPPORTED_NOTICE)

  const [nearbyResult, setNearbyResult] = useState<NearbyResult>({ key: '', data: [], error: null })
  const [topIssues, setTopIssues] = useState<IssueSummary[]>([])
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [alertsError, setAlertsError] = useState(false)
  const [weather, setWeather] = useState<WeatherNow | null>(null)
  const [air, setAir] = useState<AirNow | null>(null)

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
    const d = DISTRICTS.find((x) => x.name === name)
    if (!d) return
    setLocation({ lat: d.lat, lng: d.lng, label: d.name })
    setNotice(null)
  }

  // API-002 내 주변 이슈
  const nearbyKey = `${location.lat},${location.lng},${radiusKm},${category}`
  useEffect(() => {
    let ignore = false
    fetchNearbyIssues(location.lat, location.lng, radiusKm, category || undefined)
      .then((data) => !ignore && setNearbyResult({ key: nearbyKey, data, error: null }))
      .catch(() => !ignore && setNearbyResult({ key: nearbyKey, data: [], error: SERVER_ERROR }))
    return () => {
      ignore = true
    }
  }, [nearbyKey, location.lat, location.lng, radiusKm, category, now])
  const nearby = nearbyResult.data
  const nearbyLoading = nearbyResult.key !== nearbyKey

  // API-003 부산 주요 이슈, API-007 재난문자
  useEffect(() => {
    let ignore = false
    fetchTopIssues()
      .then((data) => !ignore && setTopIssues(data))
      .catch(() => {})
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
          <IssueMap issues={mapIssues} location={location} radiusKm={radiusKm} selectedId={selectedId} onSelect={setSelectedId} />
          {notice && (
            <div className="absolute top-3 right-3 left-14 flex items-start md:right-auto md:left-1/2 md:w-[460px] md:-translate-x-1/2 gap-2 rounded-lg border border-caution/40 bg-panel/95 px-3 py-2 text-xs shadow-lg">
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
            locating={locating}
            onUseMyLocation={locate}
            onSelectDistrict={selectDistrict}
            onRadiusChange={setRadiusKm}
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
