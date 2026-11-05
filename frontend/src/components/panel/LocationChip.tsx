import { useState, type ReactNode } from 'react'
import { PERIOD_OPTIONS } from '../../lib/constants'
import type { UserLocation } from '../../types'

interface LocationChipProps {
  location: UserLocation
  radiusKm: number
  periodDays: number
  /** 누르면 펼쳐지는 위치·반경·기간 선택 (LocationControl) */
  children: ReactNode
}

/** 모바일 지도 위 요약 칩: '📍 부산시청 · 10km · 7일'. 시트 높이와 관계없이 현재 조건이 늘 보인다 */
export default function LocationChip({ location, radiusKm, periodDays, children }: LocationChipProps) {
  const [open, setOpen] = useState(false)
  const period = PERIOD_OPTIONS.find((p) => p.days === periodDays)?.label ?? `${periodDays}일`
  const summary = [location.label, location.wholeCity ? null : `${radiusKm}km`, period].filter(Boolean).join(' · ')

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="absolute top-3 left-14 z-20 max-w-[calc(100%-11rem)] truncate rounded-full border border-line bg-panel/95 px-3 py-1.5 text-xs font-semibold shadow-lg"
      >
        📍 {summary}
      </button>
      {open && (
        <div className="absolute top-14 right-3 left-3 z-30 overflow-hidden rounded-lg border border-line bg-panel shadow-xl">
          {children}
          <button type="button" onClick={() => setOpen(false)} className="w-full border-t border-line py-2 text-xs text-muted">
            닫기
          </button>
        </div>
      )}
    </>
  )
}
