import { useEffect, useState } from 'react'

/** 미디어 쿼리가 맞는지 따라간다 (예: 데스크톱 화면 너비) */
export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(() => window.matchMedia(query).matches)
  useEffect(() => {
    const media = window.matchMedia(query)
    const onChange = () => setMatches(media.matches)
    media.addEventListener('change', onChange)
    return () => media.removeEventListener('change', onChange)
  }, [query])
  return matches
}

/** Tailwind md(768px) 이상: 지도 + 오른쪽 패널 / 미만: 지도 + 바텀시트 */
export const DESKTOP_QUERY = '(min-width: 768px)'
