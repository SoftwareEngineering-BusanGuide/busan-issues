/**
 * 화면 높이를 직접 재서 --app-height CSS 변수로 쓴다.
 *
 * iPhone 홈 화면 앱(standalone)은 처음 열릴 때 화면 높이를 실제보다 작게 알려 주고 잠시 뒤에 바로잡는데,
 * 100dvh는 이 변화를 늦게 반영하거나 놓친다. 그러면 지도가 작은 높이로 만들어져 아래쪽 절반이 검게 남는다.
 * 그래서 실행 직후 몇 번, 그리고 화면이 바뀔 때마다 다시 재고, 'app:viewport' 이벤트로 지도에 알린다.
 */
export const VIEWPORT_EVENT = 'app:viewport'

function measure(): void {
  const height = Math.round(window.visualViewport?.height ?? window.innerHeight)
  const root = document.documentElement
  if (root.style.getPropertyValue('--app-height') !== `${height}px`) {
    root.style.setProperty('--app-height', `${height}px`)
  }
  window.dispatchEvent(new Event(VIEWPORT_EVENT))
}

export function watchViewport(): void {
  measure()
  // 홈 화면 앱은 실행 직후 높이가 바뀌므로 잠시 동안 여러 번 다시 잰다
  for (const delay of [50, 300, 1000, 2500]) setTimeout(measure, delay)

  window.addEventListener('resize', measure)
  window.addEventListener('orientationchange', () => setTimeout(measure, 300))
  window.visualViewport?.addEventListener('resize', measure)
  // 다른 앱에 갔다가 돌아오거나(bfcache 포함) 화면이 다시 보일 때
  window.addEventListener('pageshow', measure)
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') {
      measure()
      setTimeout(measure, 300)
    }
  })
}
