import { formatClock, formatRelative } from '../../lib/format'
import type { Alert } from '../../types'

interface AlertTickerProps {
  alerts: Alert[]
  error: boolean
  now: number
}

const LEVEL_COLOR: Record<string, string> = { 위급재난: 'text-danger', 긴급재난: 'text-danger' }

/** UI-01 재난문자·특보 띠 (FR-007). 공공누리 제4유형이라 문자 원문은 바꾸지 않고, 지역·시각만 옆에 붙인다. */
export default function AlertTicker({ alerts, error, now }: AlertTickerProps) {
  const status = error
    ? '실시간 재난문자를 일시적으로 불러올 수 없습니다.'
    : alerts.length === 0
      ? '최근 3일간 부산 지역 재난문자가 없습니다.'
      : null

  const items = alerts.map((a) => (
    <span key={a.id} className="mx-8 whitespace-nowrap" title={`${a.level} · ${a.hazard} · ${a.source}`}>
      <span className={`font-semibold ${LEVEL_COLOR[a.level] ?? 'text-caution'}`}>[{a.sender}]</span>{' '}
      <span className="text-muted">
        {formatRelative(a.issued_at, now)} ({formatClock(a.issued_at)})
      </span>{' '}
      {a.message}
    </span>
  ))

  return (
    <footer className="flex h-10 shrink-0 items-center overflow-hidden border-t border-line bg-panel text-sm">
      <span className="z-10 flex h-full shrink-0 items-center bg-danger px-3 text-xs font-bold text-white">⚠️ 재난문자</span>
      {status ? (
        <span className="px-4 text-xs text-muted">{status}</span>
      ) : (
        <div className="ticker-mask relative flex-1 overflow-hidden">
          {/* 같은 목록을 두 번 이어 붙여 끊김 없이 흐르게 한다 */}
          <div className="ticker-track flex w-max">
            <div className="flex">{items}</div>
            <div className="flex" aria-hidden>
              {items}
            </div>
          </div>
        </div>
      )}
    </footer>
  )
}
