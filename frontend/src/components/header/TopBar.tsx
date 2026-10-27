import { formatDateTime } from '../../lib/format'

export default function TopBar({ now }: { now: number }) {
  return (
    <header className="flex h-14 shrink-0 items-center gap-3 border-b border-line bg-panel px-4">
      <span className="relative flex h-2.5 w-2.5">
        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-danger opacity-75" />
        <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-danger" />
      </span>
      <h1 className="text-base font-bold whitespace-nowrap">부산 알리미</h1>
      <span className="rounded border border-caution/50 px-1.5 py-0.5 text-[10px] font-semibold whitespace-nowrap text-caution">
        데모 데이터
      </span>
      <span className="ml-auto hidden text-sm whitespace-nowrap text-muted md:inline">{formatDateTime(new Date(now))}</span>
    </header>
  )
}
