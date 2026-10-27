import type { AirGrade, UserLocation } from '../types'

/** 위치 권한이 없을 때 쓰는 기본 위치 */
export const DEFAULT_LOCATION: UserLocation = { lat: 35.1798, lng: 129.075, label: '부산시청 (기본 위치)' }

/** 지도를 부산 주변으로 제한 [[서남], [동북]] */
export const BUSAN_BOUNDS: [[number, number], [number, number]] = [
  [128.6, 34.85],
  [129.5, 35.5],
]

/** 키 없이 쓸 수 있는 CARTO 다크 베이스맵. Kakao Maps로 바꾸기 전까지 사용 */
export const MAP_STYLE_URL =
  import.meta.env.VITE_MAP_STYLE_URL ?? 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json'

/** 위치 직접 선택용 16개 구·군 (구청·군청 좌표 기준) */
export const DISTRICTS: { name: string; lat: number; lng: number }[] = [
  { name: '중구', lat: 35.1062, lng: 129.0323 },
  { name: '서구', lat: 35.0979, lng: 129.0243 },
  { name: '동구', lat: 35.1293, lng: 129.0454 },
  { name: '영도구', lat: 35.0911, lng: 129.0679 },
  { name: '부산진구', lat: 35.1628, lng: 129.0531 },
  { name: '동래구', lat: 35.2049, lng: 129.0837 },
  { name: '남구', lat: 35.1366, lng: 129.0843 },
  { name: '북구', lat: 35.1972, lng: 128.9903 },
  { name: '해운대구', lat: 35.1631, lng: 129.1636 },
  { name: '사하구', lat: 35.1046, lng: 128.9748 },
  { name: '금정구', lat: 35.243, lng: 129.0922 },
  { name: '강서구', lat: 35.2122, lng: 128.9806 },
  { name: '연제구', lat: 35.1762, lng: 129.0799 },
  { name: '수영구', lat: 35.1455, lng: 129.1131 },
  { name: '사상구', lat: 35.1527, lng: 128.9915 },
  { name: '기장군', lat: 35.2445, lng: 129.2222 },
]

export const RADIUS_OPTIONS_KM = [2, 5, 10]

/** 이슈 기간 (최근 며칠 안에 갱신된 이슈). 서버는 최근 4주치 기사까지 모은다 */
export const PERIOD_OPTIONS = [
  { days: 1, label: '24시간' },
  { days: 7, label: '7일' },
  { days: 30, label: '30일' },
]
export const DEFAULT_PERIOD_DAYS = 7

/** 이슈 분류 (backend/app/constants.py의 CATEGORIES와 맞춘다) */
export const CATEGORY_META: Record<string, { icon: string; color: string }> = {
  '재난·안전': { icon: '⚠️', color: '#ef4444' },
  '사건·사고': { icon: '🚨', color: '#fb923c' },
  교통: { icon: '🚦', color: '#facc15' },
  '공사·생활': { icon: '🚧', color: '#38bdf8' },
  행정: { icon: '🏛️', color: '#a78bfa' },
  행사: { icon: '🎉', color: '#4ade80' },
}

export const FALLBACK_CATEGORY = { icon: '📍', color: '#8b98a8' }

export const categoryMeta = (category: string) => CATEGORY_META[category] ?? FALLBACK_CATEGORY

export const AIR_GRADE_COLOR: Record<AirGrade, string> = {
  좋음: '#38bdf8',
  보통: '#4ade80',
  나쁨: '#fb923c',
  매우나쁨: '#ef4444',
}

/** 강수가 있으면 강수 형태, 없으면 하늘 상태로 고른 아이콘 */
export function weatherIcon(precipitationType: string, sky: string | null): string {
  if (precipitationType.includes('눈')) return '🌨️'
  if (precipitationType !== '없음') return '🌧️'
  if (sky === '맑음') return '☀️'
  if (sky === '흐림') return '☁️'
  return '⛅'
}
