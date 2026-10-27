import { DISTRICTS, RADIUS_OPTIONS_KM } from '../../lib/constants'
import type { UserLocation } from '../../types'

interface LocationControlProps {
  location: UserLocation
  radiusKm: number
  locating: boolean
  onUseMyLocation: () => void
  onSelectDistrict: (name: string) => void
  onRadiusChange: (km: number) => void
}

/** UI-05 위치 설정 (FR-001): 현재 위치(브라우저 권한) 또는 구·군 직접 선택 */
export default function LocationControl({
  location,
  radiusKm,
  locating,
  onUseMyLocation,
  onSelectDistrict,
  onRadiusChange,
}: LocationControlProps) {
  const selectedDistrict = DISTRICTS.find((d) => d.name === location.label)?.name ?? ''

  return (
    <div className="space-y-2 border-b border-line px-4 py-3">
      <p className="truncate text-xs text-muted">
        📍 기준 위치 <strong className="text-foreground">{location.label}</strong>
      </p>
      <div className="flex gap-2">
        <button
          type="button"
          onClick={onUseMyLocation}
          disabled={locating}
          className="shrink-0 rounded-md border border-line bg-card px-2.5 py-1.5 text-xs hover:border-muted/60 disabled:opacity-60"
        >
          {locating ? '위치 확인 중…' : '내 위치'}
        </button>
        <select
          value={selectedDistrict}
          onChange={(e) => e.target.value && onSelectDistrict(e.target.value)}
          aria-label="구·군 선택"
          className="min-w-0 flex-1 rounded-md border border-line bg-card px-2 py-1.5 text-xs"
        >
          <option value="">구·군 선택</option>
          {DISTRICTS.map((d) => (
            <option key={d.name} value={d.name}>
              {d.name}
            </option>
          ))}
        </select>
        <select
          value={radiusKm}
          onChange={(e) => onRadiusChange(Number(e.target.value))}
          aria-label="반경"
          className="shrink-0 rounded-md border border-line bg-card px-2 py-1.5 text-xs"
        >
          {RADIUS_OPTIONS_KM.map((km) => (
            <option key={km} value={km}>
              반경 {km}km
            </option>
          ))}
        </select>
      </div>
    </div>
  )
}
