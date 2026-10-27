// 백엔드 응답 형식 (SDD 6장, backend/app/schemas.py와 맞춘다)

export interface IssueSummary {
  id: number
  title: string
  category: string
  importance: 'high' | 'normal' | string
  place_name: string | null
  lat: number | null
  lng: number | null
  /** ISO 8601 (UTC) */
  updated_at: string
}

export interface NearbyIssue extends IssueSummary {
  distance_km: number
}

export interface Article {
  id: number
  title: string
  description: string
  url: string
  published_at: string
}

export interface IssueDetail {
  issue: IssueSummary & { status_summary: string | null }
  articles: Article[]
}

export interface Alert {
  id: string
  sender: string
  message: string
  issued_at: string
  districts: string[]
  source: string
}

export interface UserLocation {
  lat: number
  lng: number
  /** 화면에 보여줄 위치 이름 (예: 해운대구, 현재 위치) */
  label: string
}
