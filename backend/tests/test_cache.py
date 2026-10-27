import pytest

from app.cache import DataUnavailable, StaleCache


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


def test_reuses_value_within_ttl_and_refetches_after():
    clock = FakeClock()
    cache = StaleCache(ttl_seconds=60, clock=clock)
    calls = []

    def fetch():
        calls.append(1)
        return len(calls)

    assert cache.get("k", fetch) == 1
    clock.t = 59
    assert cache.get("k", fetch) == 1
    clock.t = 61
    assert cache.get("k", fetch) == 2


def test_returns_last_value_when_refresh_fails():
    clock = FakeClock()
    cache = StaleCache(ttl_seconds=60, clock=clock)
    cache.get("k", lambda: "ok")
    clock.t = 120

    def broken():
        raise RuntimeError("api down")

    assert cache.get("k", broken) == "ok"


def test_raises_when_nothing_cached_and_fetch_fails():
    cache = StaleCache(ttl_seconds=60)
    with pytest.raises(DataUnavailable):
        cache.get("k", lambda: (_ for _ in ()).throw(RuntimeError("api down")))
