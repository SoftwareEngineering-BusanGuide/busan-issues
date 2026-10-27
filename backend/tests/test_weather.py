from datetime import datetime, timedelta, timezone

import httpx
from fastapi.testclient import TestClient

from app.weather import KmaWeatherProvider, base_times, to_grid

KST = timezone(timedelta(hours=9))


def test_grid_for_busan_city_hall():
    assert to_grid(35.1798, 129.0750) == (98, 76)


def test_base_times():
    ncst, fcst = base_times(datetime(2026, 10, 27, 12, 50, tzinfo=KST))
    assert (ncst.hour, ncst.minute) == (12, 0)  # 12시 자료는 12:40 이후 제공
    assert (fcst.hour, fcst.minute) == (11, 30)  # 12:30 자료는 13:15 이후 제공

    ncst, fcst = base_times(datetime(2026, 10, 27, 0, 20, tzinfo=KST))
    assert (ncst.day, ncst.hour) == (26, 23)  # 자정 직후에는 전날 자료
    assert (fcst.day, fcst.hour, fcst.minute) == (26, 23, 30)


def _kma_response(items: list[dict], code: str = "00") -> dict:
    return {"response": {"header": {"resultCode": code, "resultMsg": "MSG"}, "body": {"items": {"item": items}}}}


def _provider(fcst_status: int = 200) -> KmaWeatherProvider:
    def handler(request: httpx.Request) -> httpx.Response:
        assert (request.url.params["nx"], request.url.params["ny"]) == ("98", "76")
        if request.url.path.endswith("getUltraSrtNcst"):
            return httpx.Response(200, json=_kma_response([
                {"category": "T1H", "obsrValue": "17.2"}, {"category": "REH", "obsrValue": "33"},
                {"category": "RN1", "obsrValue": "0"}, {"category": "PTY", "obsrValue": "0"},
                {"category": "WSD", "obsrValue": "2"},
            ]))
        if fcst_status != 200:
            return httpx.Response(fcst_status)
        return httpx.Response(200, json=_kma_response([
            {"category": "SKY", "fcstDate": "20261027", "fcstTime": "1400", "fcstValue": "4"},
            {"category": "SKY", "fcstDate": "20261027", "fcstTime": "1300", "fcstValue": "3"},
        ]))

    return KmaWeatherProvider("test-key", client=httpx.Client(transport=httpx.MockTransport(handler)))


def test_provider_reads_observation_and_nearest_sky():
    w = _provider().current(35.1798, 129.0750)
    assert (w.temperature, w.humidity, w.wind_speed, w.precipitation_1h) == (17.2, 33, 2, 0)
    assert w.precipitation_type == "없음"
    assert w.sky == "구름많음"  # 13시 예보


def test_provider_still_answers_when_forecast_fails():
    w = _provider(fcst_status=500).current(35.1798, 129.0750)
    assert w.temperature == 17.2 and w.sky is None


def test_endpoint_without_key_returns_503(client: TestClient):
    assert client.get("/api/weather", params={"lat": 35.18, "lng": 129.07}).status_code == 503


def test_endpoint_uses_provider_and_validates_range(client: TestClient):
    client.app.state.weather_provider = _provider()
    res = client.get("/api/weather", params={"lat": 35.1798, "lng": 129.0750})
    assert res.status_code == 200 and res.json()["temperature"] == 17.2
    assert client.get("/api/weather", params={"lat": 37.5, "lng": 127.0}).status_code == 422  # 서울


def test_provider_reads_wind_direction():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("getUltraSrtNcst"):
            return httpx.Response(200, json=_kma_response([
                {"category": "T1H", "obsrValue": "17"}, {"category": "VEC", "obsrValue": "228"},
                {"category": "WSD", "obsrValue": "3.5"}, {"category": "PTY", "obsrValue": "0"},
            ]))
        return httpx.Response(500)

    w = KmaWeatherProvider("k", client=httpx.Client(transport=httpx.MockTransport(handler))).current(35.1798, 129.075)
    assert (w.wind_direction, w.wind_speed) == (228, 3.5)


def _grid_provider(counter: list[int], fail: bool = False) -> KmaWeatherProvider:
    """nx가 클수록 따뜻하고, 가장 남쪽 줄(ny 70 이하, 바다)이면 결측값(-999)을 주는 가짜 기상청."""

    def handler(request: httpx.Request) -> httpx.Response:
        counter.append(1)
        if fail:
            return httpx.Response(500)
        nx, ny = int(request.url.params["nx"]), int(request.url.params["ny"])
        missing = ny <= 70
        return httpx.Response(200, json=_kma_response([
            {"category": "T1H", "obsrValue": "-999" if missing else str(nx / 10)},
            {"category": "UUU", "obsrValue": "-998.9" if missing else "1.5"},
            {"category": "VVV", "obsrValue": "-998.9" if missing else "-2"},
        ]))

    return KmaWeatherProvider("k", client=httpx.Client(transport=httpx.MockTransport(handler)))


def test_grid_shape_values_and_missing_sea_cells():
    from app.weather import GRID_LATS, GRID_LNGS

    counter: list[int] = []
    grid = _grid_provider(counter).grid()
    assert len(grid.temperature) == len(GRID_LATS) and len(grid.temperature[0]) == len(GRID_LNGS)
    assert grid.lats == sorted(grid.lats) and grid.lngs == sorted(grid.lngs)
    # 남서쪽 끝(바다)은 결측 → None, 북쪽 칸은 값이 있다
    assert grid.temperature[0][-1] is None and grid.u[0][-1] is None
    assert grid.temperature[-1][0] is not None and (grid.u[-1][0], grid.v[-1][0]) == (1.5, -2)
    # 동쪽으로 갈수록 nx가 커져 기온이 높다
    assert grid.temperature[-1][-1] > grid.temperature[-1][0]
    assert len(counter) == len(GRID_LATS) * len(GRID_LNGS)


def test_grid_is_fetched_once_per_base_time(monkeypatch):
    import app.weather as weather

    base = datetime(2026, 10, 27, 12, tzinfo=KST)
    monkeypatch.setattr(weather, "base_times", lambda now: (base, base))
    counter: list[int] = []
    provider = _grid_provider(counter)
    provider.grid()
    first = len(counter)
    provider.grid()
    assert len(counter) == first  # 같은 발표 시각이면 다시 받지 않는다


def test_grid_falls_back_to_previous_hour_when_new_fetch_fails(monkeypatch):
    import app.weather as weather

    bases = iter([datetime(2026, 10, 27, 12, tzinfo=KST), datetime(2026, 10, 27, 13, tzinfo=KST)])
    current = {}
    monkeypatch.setattr(weather, "base_times", lambda now: (current["b"], current["b"]))
    counter: list[int] = []
    provider = _grid_provider(counter)
    current["b"] = next(bases)
    previous = provider.grid()
    # 13시 자료는 모두 실패 → 12시 격자를 그대로 보여준다
    provider._client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(500)))
    current["b"] = next(bases)
    assert provider.grid().observed_at == previous.observed_at


def test_grid_endpoint(client: TestClient):
    assert client.get("/api/weather/grid").status_code == 503  # 키 없음
    client.app.state.weather_provider = _grid_provider([])
    body = client.get("/api/weather/grid").json()
    assert set(body) >= {"lats", "lngs", "temperature", "u", "v", "observed_at", "source"}
    assert client.get("/api/weather/districts").status_code == 404  # 격자 API로 바뀜
