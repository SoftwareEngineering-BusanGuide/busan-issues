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
