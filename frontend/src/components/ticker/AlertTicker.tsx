import { formatClock } from '../../lib/format'
import type { Alert } from '../../types'

/** UI-01 재난문자·특보 배너 (FR-007). 공공누리 제4유형이라 문구를 바꾸지 않고 원문 그대로 보여준다. */
export default function AlertTicker({ alerts }: { alerts: Alert[] }) {
  if (alerts.length === 0) return null
  const items = alerts.map((a) => (
    // 발신처는 원문 앞에 이미 들어 있어서 따로 붙이지 않는다
    <span key={a.id} className="mx-8 whitespace-nowrap" title={a.sender}>
      <span className="font-semibold text-danger">{formatClock(a.issued_at)}</span> {a.message}
    </span>
  ))

  return (
    <footer className="flex h-10 shrink-0 items-center overflow-hidden border-t border-line bg-panel text-sm" title={alerts[0].source}>
      <span className="z-10 flex h-full shrink-0 items-center bg-danger px-3 text-xs font-bold text-white">⚠️ 재난문자·특보</span>
      <div className="ticker-mask relative flex-1 overflow-hidden">
        {/* 같은 목록을 두 번 이어 붙여 끊김 없이 흐르게 한다 */}
        <div className="ticker-track flex w-max">
          <div className="flex">{items}</div>
          <div className="flex" aria-hidden>
            {items}
          </div>
        </div>
      </div>
    </footer>
  )
}
