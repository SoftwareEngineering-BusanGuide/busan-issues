import { useRef, useState, type PointerEvent, type ReactNode } from 'react'

export type SheetSnap = 'peek' | 'half' | 'full'

interface BottomSheetProps {
  snap: SheetSnap
  onSnapChange: (snap: SheetSnap) => void
  /** 손잡이 옆 제목 줄 (살짝 내렸을 때도 보임) */
  title: ReactNode
  children: ReactNode
}

/** 살짝 내렸을 때 높이: 손잡이 + 제목 줄 (+ 홈바 여백은 CSS로 더한다) */
const PEEK_PX = 54
/** 전체로 올렸을 때 위쪽에 남길 지도 높이 */
const FULL_GAP_PX = 12
const TAP_PX = 6

/**
 * 모바일 바텀시트: 지도 위에 겹쳐 아래에서 끌어올린다. 높이는 살짝 → 절반 → 전체 세 단계.
 * 제목 줄을 끌어 높이를 바꾸고, 눌러서 한 단계씩 바꾼다. 부모(지도 영역)를 기준으로 높이를 정한다.
 */
export default function BottomSheet({ snap, onSnapChange, title, children }: BottomSheetProps) {
  const sheetRef = useRef<HTMLDivElement>(null)
  const drag = useRef<{ startY: number; startHeight: number; height: number; moved: boolean } | null>(null)
  const [dragHeight, setDragHeight] = useState<number | null>(null)

  const parentHeight = () => sheetRef.current?.parentElement?.clientHeight ?? window.innerHeight
  const snapHeights = (): Record<SheetSnap, number> => {
    const h = parentHeight()
    return { peek: PEEK_PX, half: h * 0.5, full: h - FULL_GAP_PX }
  }

  const onPointerDown = (e: PointerEvent<HTMLDivElement>) => {
    e.currentTarget.setPointerCapture(e.pointerId)
    const startHeight = sheetRef.current?.getBoundingClientRect().height ?? PEEK_PX
    drag.current = { startY: e.clientY, startHeight, height: startHeight, moved: false }
  }

  const onPointerMove = (e: PointerEvent<HTMLDivElement>) => {
    const d = drag.current
    if (!d) return
    const dy = e.clientY - d.startY
    if (Math.abs(dy) > TAP_PX) d.moved = true
    if (!d.moved) return
    const { peek, full } = snapHeights()
    d.height = Math.min(Math.max(d.startHeight - dy, peek), full)
    setDragHeight(d.height)
  }

  const onPointerUp = () => {
    const d = drag.current
    drag.current = null
    if (!d) return
    if (!d.moved) {
      // 누르기: 살짝 → 절반 → 전체, 전체에서 누르면 절반으로
      onSnapChange(snap === 'peek' ? 'half' : snap === 'half' ? 'full' : 'half')
      return
    }
    // 끌기를 놓으면 가장 가까운 단계로 붙는다 (state는 마지막 움직임을 아직 반영하지 않았을 수 있어 ref 값을 쓴다)
    const heights = snapHeights()
    const current = d.height
    const nearest = (Object.keys(heights) as SheetSnap[]).reduce((best, key) =>
      Math.abs(heights[key] - current) < Math.abs(heights[best] - current) ? key : best,
    )
    setDragHeight(null)
    onSnapChange(nearest)
  }

  const height =
    dragHeight != null
      ? `${dragHeight}px`
      : snap === 'peek'
        ? `calc(${PEEK_PX}px + env(safe-area-inset-bottom))`
        : snap === 'half'
          ? '50%'
          : `calc(100% - ${FULL_GAP_PX}px)`

  return (
    <div
      ref={sheetRef}
      className="absolute inset-x-0 bottom-0 z-30 flex flex-col rounded-t-2xl border-t border-line bg-panel shadow-[0_-8px_24px_rgb(0_0_0/0.45)]"
      style={{ height, transition: dragHeight != null ? 'none' : 'height 0.25s ease', paddingBottom: 'env(safe-area-inset-bottom)' }}
    >
      {/* 끌거나 누르는 영역: 페이지가 함께 스크롤되지 않게 touch-action을 막는다 */}
      <div
        role="button"
        tabIndex={0}
        aria-label="목록 높이 바꾸기"
        className="shrink-0 cursor-grab touch-none px-4 pt-2 pb-3 select-none"
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') onSnapChange(snap === 'peek' ? 'half' : snap === 'half' ? 'full' : 'peek')
        }}
      >
        <div className="mx-auto mb-2 h-1 w-10 rounded-full bg-muted/50" />
        <div className="flex items-center justify-between text-sm font-bold">{title}</div>
      </div>
      <div className="flex min-h-0 flex-1 flex-col overflow-hidden">{children}</div>
    </div>
  )
}
