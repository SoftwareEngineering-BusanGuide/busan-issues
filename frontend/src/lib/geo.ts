import type { Feature, Polygon } from 'geojson'
import { BUSAN_BOUNDS } from './constants'

/** 대략적인 부산 범위 안인지 (UC-001 대안 흐름 2a: 부산 밖이면 기본 위치로) */
export function isInBusan(lat: number, lng: number): boolean {
  const [[west, south], [east, north]] = BUSAN_BOUNDS
  return lat >= south && lat <= north && lng >= west && lng <= east
}

/** 지도에 그릴 반경 원 (GeoJSON 폴리곤 근사) */
export function circlePolygon(lat: number, lng: number, radiusKm: number, steps = 64): Feature<Polygon> {
  const coords: [number, number][] = []
  const dLat = radiusKm / 110.574
  const dLng = radiusKm / (111.32 * Math.cos((lat * Math.PI) / 180))
  for (let i = 0; i <= steps; i++) {
    const t = (i / steps) * 2 * Math.PI
    coords.push([lng + dLng * Math.cos(t), lat + dLat * Math.sin(t)])
  }
  return { type: 'Feature', properties: {}, geometry: { type: 'Polygon', coordinates: [coords] } }
}
