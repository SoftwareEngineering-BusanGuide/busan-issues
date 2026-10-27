import type { AirNow, Alert, IssueDetail, IssueSummary, NearbyIssue, WeatherNow } from '../types'

async function getJson<T>(path: string, params?: Record<string, string | number | undefined>): Promise<T> {
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(params ?? {})) {
    if (value !== undefined && value !== '') query.set(key, String(value))
  }
  const qs = query.toString()
  const res = await fetch(qs ? `${path}?${qs}` : path)
  if (!res.ok) throw new Error(`${path} 요청 실패 (${res.status})`)
  return res.json() as Promise<T>
}

/** API-002 내 주변 이슈 */
export const fetchNearbyIssues = (lat: number, lng: number, radius: number, category?: string) =>
  getJson<NearbyIssue[]>('/api/issues/nearby', { lat, lng, radius, category })

/** API-003 부산 주요 이슈 */
export const fetchTopIssues = () => getJson<IssueSummary[]>('/api/issues/top')

/** API-004 이슈 상세 */
export const fetchIssueDetail = (id: number) => getJson<IssueDetail>(`/api/issues/${id}`)

/** API-007 재난문자·기상특보 */
export const fetchAlerts = () => getJson<Alert[]>('/api/alerts')

/** 기준 위치의 현재 날씨 (기상청) */
export const fetchWeather = (lat: number, lng: number) => getJson<WeatherNow>('/api/weather', { lat, lng })

/** 기준 위치에서 가장 가까운 측정소의 미세먼지 (에어코리아) */
export const fetchAir = (lat: number, lng: number) => getJson<AirNow>('/api/air', { lat, lng })
