"""대화형 질의 요청 횟수 제한. 공개 서비스라 Gemini 무료 한도를 한 사람이 다 쓰지 못하게 한다 (deployment.md 주의 사항)."""

import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable


class RateLimiter:
    """IP별 분당·하루 횟수와, 서비스 전체 하루 횟수를 메모리에서 센다. 서버가 재시작하면 초기화된다."""

    def __init__(self, per_minute: int, per_day: int, total_per_day: int, clock: Callable[[], float] = time.time):
        self._limits = ((60, per_minute), (86400, per_day))
        self._total_per_day = total_per_day
        self._clock = clock
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._total: deque[float] = deque()
        self._lock = threading.Lock()

    def check(self, key: str) -> str | None:
        """허용하면 기록하고 None, 막으면 이유를 돌려준다."""
        now = self._clock()
        with self._lock:
            hits = self._hits[key]
            for q in (hits, self._total):
                while q and now - q[0] >= 86400:
                    q.popleft()
            if len(self._total) >= self._total_per_day:
                return "오늘 질문 가능 횟수를 모두 썼습니다. 내일 다시 이용해 주세요."
            for window, limit in self._limits:
                if sum(1 for t in hits if now - t < window) >= limit:
                    return "질문이 너무 잦습니다. 잠시 후 다시 물어봐 주세요." if window == 60 else "오늘 질문 가능 횟수를 모두 썼습니다."
            hits.append(now)
            self._total.append(now)
            return None
