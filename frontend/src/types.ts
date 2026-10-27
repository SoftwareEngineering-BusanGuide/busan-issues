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
  /** 수신 지역 표시 (예: 부산 북구). message는 원문 그대로다. */
  sender: string
  message: string
  issued_at: string
  /** 비어 있으면 부산 전체 */
  districts: string[]
  /** 안전안내 / 긴급재난 / 위급재난 */
  level: string
  /** 재난 유형 (예: 호우) */
  hazard: string
  source: string
}

export interface WeatherNow {
  temperature: number | null
  humidity: number | null
  precipitation_1h: number | null
  /** 없음 / 비 / 비/눈 / 눈 / 빗방울 ... */
  precipitation_type: string
  /** 맑음 / 구름많음 / 흐림 */
  sky: string | null
  wind_speed: number | null
  /** 바람이 불어오는 방향 (도, 북=0 시계방향) */
  wind_direction: number | null
  observed_at: string
  source: string
}

export interface DistrictWeather {
  district: string
  lat: number
  lng: number
  weather: WeatherNow
}

export interface AirStation {
  station: string
  lat: number
  lng: number
  pm10: number | null
  pm25: number | null
  pm10_grade: AirGrade | null
  pm25_grade: AirGrade | null
  grade: AirGrade | null
  measured_at: string
}

/** 지도 레이어 켜짐 여부 */
export interface MapLayers {
  issues: boolean
  satellite: boolean
  weather: boolean
  wind: boolean
  air: boolean
}

export type AirGrade = '좋음' | '보통' | '나쁨' | '매우나쁨'

export interface AirNow {
  station: string
  distance_km: number
  pm10: number | null
  pm25: number | null
  pm10_grade: AirGrade | null
  pm25_grade: AirGrade | null
  grade: AirGrade | null
  measured_at: string
  source: string
}

export interface UserLocation {
  lat: number
  lng: number
  /** 화면에 보여줄 위치 이름 (예: 해운대구, 현재 위치) */
  label: string
}
