import type {
  AirNow,
  AirStation,
  Alert,
  ChatReply,
  IssueDetail,
  IssueSummary,
  NearbyIssue,
  UserLocation,
  WeatherGrid,
  WeatherNow,
} from '../types'

// ── 서버 상태 ──────────────────────────────────────────────
// Render 무료 서버는 잠들었다 깨는 데 30초~1분 걸린다. 그동안 화면에 '깨우는 중'을 보여주려고 상태를 알린다.
let serverWaking = false
const statusListeners = new Set<() => void>()
function setServerWaking(value: boolean) {
  if (serverWaking === value) return
  serverWaking = value
  statusListeners.forEach((listener) => listener())
}
/** useSyncExternalStore용: 서버가 깨는 중인지 */
export const serverStatus = {
  subscribe(listener: () => void) {
    statusListeners.add(listener)
    return () => {
      statusListeners.delete(listener)
    }
  },
  isWaking: () => serverWaking,
}

// ── 기기에 저장한 마지막 응답 ──────────────────────────────
// 앱을 열면 저장된 값을 먼저 보여주고, 서버 응답이 오면 바꾼다. 너무 오래된 값은 쓰지 않는다.
const CACHE_PREFIX = 'busan-alimi:api:'
const CACHE_MAX_AGE_MS = 12 * 60 * 60 * 1000
const CACHE_MAX_ENTRIES = 40

function readCache<T>(url: string): T | undefined {
  try {
    const raw = localStorage.getItem(CACHE_PREFIX + url)
    if (!raw) return undefined
    const { at, data } = JSON.parse(raw) as { at: number; data: T }
    return Date.now() - at < CACHE_MAX_AGE_MS ? data : undefined
  } catch {
    return undefined
  }
}

function writeCache(url: string, data: unknown) {
  try {
    localStorage.setItem(CACHE_PREFIX + url, JSON.stringify({ at: Date.now(), data }))
    // 위치·기간을 바꿀 때마다 쌓이므로 오래된 것부터 지운다
    const keys = Object.keys(localStorage).filter((k) => k.startsWith(CACHE_PREFIX))
    if (keys.length > CACHE_MAX_ENTRIES) {
      const byAge = keys.map((k) => [k, (JSON.parse(localStorage.getItem(k) ?? '{}') as { at?: number }).at ?? 0] as const)
      byAge.sort((a, b) => a[1] - b[1])
      byAge.slice(0, keys.length - CACHE_MAX_ENTRIES).forEach(([k]) => localStorage.removeItem(k))
    }
  } catch {
    // 저장 공간이 없거나 막혀 있어도(사파리 개인 정보 보호 모드 등) 화면은 그대로 동작한다
  }
}

// ── 요청 ───────────────────────────────────────────────────
/** 서버가 깨는 동안 다시 시도하는 간격 (합계 약 45초) */
const RETRY_DELAYS_MS = [2_000, 4_000, 8_000, 15_000, 15_000]
/** 이보다 오래 걸리면 서버가 깨는 중으로 본다 */
const SLOW_MS = 4_000

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))

/** 서버가 깨는 중이거나 잠깐 연결이 안 될 때의 응답. 우리 서버가 일부러 준 오류(JSON, 예: 재난문자 503)는 다시 시도하지 않는다 */
function isTransient(res: Response | null): boolean {
  if (!res) return true // 네트워크 오류
  if (![500, 502, 503, 504].includes(res.status)) return false
  return !res.headers.get('content-type')?.includes('application/json')
}

async function fetchWithRetry(url: string): Promise<Response | null> {
  const slow = setTimeout(() => setServerWaking(true), SLOW_MS)
  try {
    for (let attempt = 0; ; attempt++) {
      const res = await fetch(url).catch(() => null)
      if (!isTransient(res) || attempt >= RETRY_DELAYS_MS.length) return res
      setServerWaking(true)
      await sleep(RETRY_DELAYS_MS[attempt])
    }
  } finally {
    clearTimeout(slow)
  }
}

/**
 * GET 요청. onCached를 주면 기기에 저장된 마지막 응답을 먼저 넘기고(있을 때만), 서버 응답으로 다시 넘긴다.
 * 서버가 깨는 중이면 잠시 기다렸다 다시 시도한다.
 */
async function getJson<T>(
  path: string,
  params?: Record<string, string | number | undefined>,
  onCached?: (data: T) => void,
): Promise<T> {
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(params ?? {})) {
    if (value !== undefined && value !== '') query.set(key, String(value))
  }
  const qs = query.toString()
  const url = qs ? `${path}?${qs}` : path
  if (onCached) {
    const cached = readCache<T>(url)
    if (cached !== undefined) onCached(cached)
  }

  const res = await fetchWithRetry(url)
  if (!res) throw new Error(`${path} 연결 실패`)
  if (!res.ok) throw new Error(`${path} 요청 실패 (${res.status})`)
  setServerWaking(false)
  const data = (await res.json()) as T
  if (onCached) writeCache(url, data)
  return data
}

/** API-002 내 주변 이슈 */
export const fetchNearbyIssues = (
  lat: number,
  lng: number,
  radius: number,
  days: number,
  category?: string,
  onCached?: (data: NearbyIssue[]) => void,
) => getJson<NearbyIssue[]>('/api/issues/nearby', { lat, lng, radius, days, category }, onCached)

/** API-003 부산 주요 이슈 */
export const fetchTopIssues = (days: number, onCached?: (data: IssueSummary[]) => void) =>
  getJson<IssueSummary[]>('/api/issues/top', { days }, onCached)

/** API-004 이슈 상세 */
export const fetchIssueDetail = (id: number, onCached?: (data: IssueDetail) => void) =>
  getJson<IssueDetail>(`/api/issues/${id}`, undefined, onCached)

/** API-007 재난문자·기상특보. 지난 문자를 지금 문자처럼 보이지 않게 기기에 저장하지 않는다 */
export const fetchAlerts = () => getJson<Alert[]>('/api/alerts')

/** 기준 위치의 현재 날씨 (기상청) */
export const fetchWeather = (lat: number, lng: number, onCached?: (data: WeatherNow) => void) =>
  getJson<WeatherNow>('/api/weather', { lat, lng }, onCached)

/** 기준 위치에서 가장 가까운 측정소의 미세먼지 (에어코리아) */
export const fetchAir = (lat: number, lng: number, onCached?: (data: AirNow) => void) =>
  getJson<AirNow>('/api/air', { lat, lng }, onCached)

/** 지도 기온·바람 레이어: 부산 일대 격자 실황 (매시 갱신) */
export const fetchWeatherGrid = (onCached?: (data: WeatherGrid) => void) =>
  getJson<WeatherGrid>('/api/weather/grid', undefined, onCached)

/** 지도 미세먼지 레이어: 측정소별 실시간 값 */
export const fetchAirStations = (onCached?: (data: AirStation[]) => void) =>
  getJson<AirStation[]>('/api/air/stations', undefined, onCached)

export interface ChatTurn {
  role: 'user' | 'assistant'
  text: string
}

/** API-006 대화형 질의. 실패하면 서버가 준 안내 문구(요청 제한 등)를 오류 메시지로 쓴다 */
export async function postChat(message: string, history: ChatTurn[], location: UserLocation): Promise<ChatReply> {
  const res = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message,
      history,
      location: { lat: location.lat, lng: location.lng, label: location.label.slice(0, 50) },
    }),
  })
  if (!res.ok) {
    const detail = await res.json().then((b: { detail?: unknown }) => b.detail).catch(() => null)
    throw new Error(typeof detail === 'string' ? detail : '답변을 받지 못했습니다. 잠시 후 다시 물어봐 주세요.')
  }
  return res.json() as Promise<ChatReply>
}
