/** "방금 전", "12분 전", "3시간 전", "2일 전" */
export function formatRelative(iso: string, now: number): string {
  const diffMin = Math.max(0, Math.round((now - new Date(iso).getTime()) / 60_000))
  if (diffMin < 1) return '방금 전'
  if (diffMin < 60) return `${diffMin}분 전`
  const hours = Math.floor(diffMin / 60)
  if (hours < 24) return `${hours}시간 전`
  return `${Math.floor(hours / 24)}일 전`
}

/** "18:42" */
export function formatClock(iso: string): string {
  return new Date(iso).toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', hour12: false })
}

/** "10월 27일 (월) 18:42" */
export function formatDateTime(date: Date): string {
  return date.toLocaleString('ko-KR', {
    month: 'long',
    day: 'numeric',
    weekday: 'short',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
}

/** 0.4 → "400m", 1.23 → "1.2km" */
export function formatDistance(km: number): string {
  return km < 1 ? `${Math.round(km * 1000)}m` : `${km.toFixed(1)}km`
}
