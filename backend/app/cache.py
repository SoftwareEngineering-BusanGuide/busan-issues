import threading
import time
from collections.abc import Callable
from typing import Generic, TypeVar

T = TypeVar("T")


class DataUnavailable(Exception):
    """외부 데이터를 가져오지 못했고 보여줄 이전 값도 없을 때."""


class StaleCache(Generic[T]):
    """키별로 TTL 동안 값을 재사용하고, 새로 가져오다 실패하면 마지막 성공 값을 돌려준다 (NFR-008).

    외부 API 호출 한도를 아끼고, 일시적인 장애에도 화면이 비지 않게 하려는 용도다.
    """

    def __init__(self, ttl_seconds: float, clock: Callable[[], float] = time.monotonic):
        self._ttl = ttl_seconds
        self._clock = clock
        self._entries: dict[object, tuple[float, T]] = {}
        self._lock = threading.Lock()

    def get(self, key: object, fetch: Callable[[], T]) -> T:
        with self._lock:
            entry = self._entries.get(key)
        if entry and self._clock() - entry[0] < self._ttl:
            return entry[1]
        try:
            value = fetch()
        except Exception as e:
            if entry:
                return entry[1]
            raise DataUnavailable(str(e)) from e
        with self._lock:
            self._entries[key] = (self._clock(), value)
        return value
