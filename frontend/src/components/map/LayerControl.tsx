import { useState } from 'react'
import { AIR_GRADE_COLOR, LAYER_OPTIONS, windColor } from '../../lib/constants'
import type { MapLayers } from '../../types'

interface LayerControlProps {
  layers: MapLayers
  onToggle: (key: keyof MapLayers) => void
  /** 레이어 데이터를 불러오지 못한 경우 (예: 키 없음, 외부 API 장애) */
  unavailable: Partial<Record<keyof MapLayers, boolean>>
}

/** 지도 오른쪽 위 레이어 패널: 뉴스 이슈·위성사진·날씨·바람·미세먼지를 켜고 끈다 */
export default function LayerControl({ layers, onToggle, unavailable }: LayerControlProps) {
  const [open, setOpen] = useState(false)
  const activeCount = LAYER_OPTIONS.filter((l) => l.key !== 'issues' && layers[l.key]).length

  return (
    <div className="absolute top-3 right-3 z-20 flex flex-col items-end gap-2">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="rounded-md border border-line bg-panel/95 px-3 py-1.5 text-xs font-semibold shadow-lg hover:border-muted/60"
      >
        🗂️ 레이어{activeCount > 0 && <span className="ml-1 text-accent">{activeCount}</span>}
      </button>

      {open && (
        <div className="w-48 rounded-lg border border-line bg-panel/95 p-2 text-xs shadow-lg backdrop-blur">
          {LAYER_OPTIONS.map((l) => (
            <label key={l.key} className="flex cursor-pointer items-center gap-2 rounded px-2 py-1.5 hover:bg-card">
              <input type="checkbox" checked={layers[l.key]} onChange={() => onToggle(l.key)} className="accent-sky-400" />
              <span>{l.icon}</span>
              <span className="flex-1">{l.label}</span>
              {layers[l.key] && unavailable[l.key] && <span className="text-[10px] text-danger">불러올 수 없음</span>}
            </label>
          ))}

          {/* 켜진 레이어의 범례 */}
          {layers.air && (
            <div className="mt-1 border-t border-line px-2 pt-2">
              <p className="mb-1 text-[10px] text-muted">미세먼지 등급 (PM10·PM2.5 중 나쁜 쪽)</p>
              <div className="flex flex-wrap gap-x-2 gap-y-1">
                {Object.entries(AIR_GRADE_COLOR).map(([grade, color]) => (
                  <span key={grade} className="flex items-center gap-1 text-[10px]">
                    <span className="h-2 w-2 rounded-full" style={{ background: color }} />
                    {grade}
                  </span>
                ))}
              </div>
            </div>
          )}
          {layers.wind && (
            <div className="mt-1 border-t border-line px-2 pt-2">
              <p className="mb-1 text-[10px] text-muted">풍속 (화살표: 바람이 불어 가는 방향)</p>
              <div className="flex flex-wrap gap-x-2 gap-y-1">
                {[
                  ['4 미만', 0],
                  ['4~9', 4],
                  ['9~14', 9],
                  ['14 이상', 14],
                ].map(([label, speed]) => (
                  <span key={label} className="flex items-center gap-1 text-[10px]">
                    <span className="h-2 w-2 rounded-full" style={{ background: windColor(Number(speed)) }} />
                    {label}
                  </span>
                ))}
              </div>
            </div>
          )}
          {(layers.weather || layers.wind) && (
            <p className="mt-1 px-2 text-[10px] text-muted">날씨·바람: 기상청 초단기실황 (5km 격자)</p>
          )}
        </div>
      )}
    </div>
  )
}
