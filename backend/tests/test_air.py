import httpx
from fastapi.testclient import TestClient

from app.air import AirKoreaProvider, pm10_grade, pm25_grade

YEONSAN = (35.18592, 129.10938)  # 연산동 측정소 바로 옆


def _provider(readings: list[dict]) -> AirKoreaProvider:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"response": {"header": {"resultCode": "00", "resultMsg": "OK"},
                                                      "body": {"items": readings}}})

    return AirKoreaProvider("test-key", client=httpx.Client(transport=httpx.MockTransport(handler)))


def _reading(station: str, pm10: str, pm25: str, time: str = "2026-10-27 13:00") -> dict:
    return {"stationName": station, "pm10Value": pm10, "pm25Value": pm25, "dataTime": time}


def test_grades_follow_ministry_thresholds():
    assert [pm10_grade(v) for v in (30, 31, 80, 81, 150, 151)] == ["좋음", "보통", "보통", "나쁨", "나쁨", "매우나쁨"]
    assert [pm25_grade(v) for v in (15, 16, 35, 36, 75, 76)] == ["좋음", "보통", "보통", "나쁨", "나쁨", "매우나쁨"]


def test_nearest_station_and_worse_grade():
    air = _provider([_reading("광복동", "10", "5"), _reading("연산동", "25", "20")]).nearest(*YEONSAN)
    assert air.station == "연산동" and air.distance_km < 0.1
    assert (air.pm10_grade, air.pm25_grade, air.grade) == ("좋음", "보통", "보통")


def test_skips_station_under_maintenance():
    # 연산동이 점검 중("-")이면 그다음 가까운 측정소
    air = _provider([_reading("연산동", "-", "-"), _reading("명장동", "40", "10")]).nearest(*YEONSAN)
    assert air.station == "명장동" and air.pm10 == 40


def test_midnight_is_reported_as_24_00():
    air = _provider([_reading("연산동", "10", "5", time="2026-10-27 24:00")]).nearest(*YEONSAN)
    assert (air.measured_at.day, air.measured_at.hour) == (28, 0)


def test_endpoint(client: TestClient):
    assert client.get("/api/air", params={"lat": YEONSAN[0], "lng": YEONSAN[1]}).status_code == 503  # 키 없음
    client.app.state.air_provider = _provider([_reading("연산동", "-", "-")])
    assert client.get("/api/air", params={"lat": YEONSAN[0], "lng": YEONSAN[1]}).status_code == 503  # 값 없음
    client.app.state.air_provider = _provider([_reading("연산동", "25", "20")])
    assert client.get("/api/air", params={"lat": YEONSAN[0], "lng": YEONSAN[1]}).json()["grade"] == "보통"


def test_stations_lists_every_station_with_values(client: TestClient):
    assert client.get("/api/air/stations").status_code == 503  # 키 없음
    client.app.state.air_provider = _provider([
        _reading("연산동", "25", "20"), _reading("광복동", "-", "-"), _reading("부산항", "90", "40"),
    ])
    body = client.get("/api/air/stations").json()
    # 점검 중(광복동)과 좌표표에 없는 항만 측정소(부산항)는 빠진다
    assert [s["station"] for s in body] == ["연산동"]
    assert body[0]["grade"] == "보통" and body[0]["lat"] == YEONSAN[0]
