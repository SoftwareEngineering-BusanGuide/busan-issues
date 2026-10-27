import type { Alert, IssueDetail, IssueSummary, NearbyIssue } from '../types'

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
