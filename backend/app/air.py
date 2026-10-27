"""한국환경공단 에어코리아 대기오염정보: 가장 가까운 측정소의 실시간 미세먼지."""

from datetime import datetime, timedelta, timezone

import httpx

from app.cache import StaleCache
from app.geo import distance_km
from app.schemas import AirOut, AirStationOut

KST = timezone(timedelta(hours=9))
AIRKOREA_URL = "https://apis.data.go.kr/B552584/ArpltnInforInqireSvc/getCtprvnRltmMesureDnsty"
SOURCE = "한국환경공단 에어코리아 대기오염정보 (공공데이터포털)"

# 부산 생활권 측정소 좌표 (동 단위 근사값). 측정소정보 API를 아직 신청하지 않아,
# 측정소 이름(동)을 네이버 지역 검색으로 한 번 찾아 정리했다. 항만 측정소(부산항·부산북항·부산감만)는
# 생활권 대기를 대표하지 않아 뺐다. 측정소가 바뀌면 이 표를 갱신하거나 측정소정보 API로 대체한다.
STATIONS: dict[str, tuple[float, float]] = {
    "광복동": (35.10003, 129.03044), "초량동": (35.12133, 129.03980), "태종대": (35.05378, 129.08604),
    "청학동": (35.09688, 129.05840), "전포동": (35.15442, 129.06738), "온천동": (35.22007, 129.08010),
    "명장동": (35.20474, 129.10421), "대연동": (35.13989, 129.10390), "용호동": (35.11282, 129.11166),
    "학장동": (35.14232, 128.98737), "덕천동": (35.20995, 129.01743), "화명동": (35.23276, 129.01382),
    "삼락동": (35.17436, 128.97930), "우동": (35.15971, 129.14330), "감천동": (35.08842, 129.00283),
    "청룡동": (35.27526, 129.08983), "좌동": (35.17091, 129.17419), "재송동": (35.18462, 129.12510),
    "장림동": (35.08307, 128.96689), "대저동": (35.21547, 128.97683), "녹산동": (35.15350, 128.88377),
    "명지동": (35.10017, 128.90705), "연산동": (35.18592, 129.10938), "기장읍": (35.24450, 129.22220),
    "용수리": (35.32716, 129.18013), "수정동": (35.12998, 129.04260), "회동동": (35.22040, 129.11133),
    "광안동": (35.15575, 129.11382), "대신동": (35.11301, 129.01600), "덕포동": (35.17449, 128.98293),
    "개금동": (35.15577, 129.02193), "당리동": (35.10401, 128.97457),
}

GRADES = ("좋음", "보통", "나쁨", "매우나쁨")


def pm10_grade(value: int) -> str:
    """환경부 예보 등급 기준 (㎍/㎥)."""
    return GRADES[0 if value <= 30 else 1 if value <= 80 else 2 if value <= 150 else 3]


def pm25_grade(value: int) -> str:
    return GRADES[0 if value <= 15 else 1 if value <= 35 else 2 if value <= 75 else 3]


def _value(raw: object) -> int | None:
    # 점검·통신장애 중에는 "-" 등으로 온다
    try:
        return int(float(str(raw)))
    except (TypeError, ValueError):
        return None


def _measured_at(raw: str) -> datetime:
    # "2026-10-27 13:00". 자정은 "24:00"으로 오기도 한다.
    day, hm = raw.split(" ")
    hour, minute = map(int, hm.split(":"))
    base = datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=KST)
    return base + timedelta(hours=hour, minutes=minute)


def _station(name: str, lat: float, lng: float, reading: dict | None) -> AirStationOut | None:
    """측정값 하나를 등급과 함께 정리한다. 점검 중이라 값이 없으면 None."""
    if not reading:
        return None
    pm10, pm25 = _value(reading.get("pm10Value")), _value(reading.get("pm25Value"))
    if pm10 is None and pm25 is None:
        return None
    g10 = pm10_grade(pm10) if pm10 is not None else None
    g25 = pm25_grade(pm25) if pm25 is not None else None
    return AirStationOut(
        station=name, lat=lat, lng=lng, pm10=pm10, pm25=pm25, pm10_grade=g10, pm25_grade=g25,
        grade=max((g for g in (g10, g25) if g), key=GRADES.index),
        measured_at=_measured_at(reading["dataTime"]),
    )


class AirKoreaProvider:
    def __init__(self, api_key: str, client: httpx.Client | None = None):
        self._api_key = api_key
        self._client = client or httpx.Client(timeout=10)
        # 측정값은 한 시간에 한 번 바뀐다
        self._cache: StaleCache[list[dict]] = StaleCache(ttl_seconds=600)

    def stations(self) -> list[AirStationOut]:
        """좌표를 아는 측정소 중 값이 있는 곳 전부 (지도 레이어용)."""
        readings = {r["stationName"]: r for r in self._cache.get("busan", self._fetch)}
        result = []
        for name, (lat, lng) in STATIONS.items():
            station = _station(name, lat, lng, readings.get(name))
            if station:
                result.append(station)
        return result

    def nearest(self, lat: float, lng: float) -> AirOut:
        readings = {r["stationName"]: r for r in self._cache.get("busan", self._fetch)}
        candidates = sorted(
            (distance_km(lat, lng, *coords), name) for name, coords in STATIONS.items() if name in readings
        )
        # 가까운 순으로, 미세먼지 값이 있는 측정소를 고른다
        for dist, name in candidates:
            station = _station(name, *STATIONS[name], readings[name])
            if station:
                return AirOut(**station.model_dump(exclude={"lat", "lng"}), distance_km=round(dist, 2), source=SOURCE)
        raise LookupError("미세먼지 값을 제공하는 측정소가 없습니다.")

    def _fetch(self) -> list[dict]:
        res = self._client.get(AIRKOREA_URL, params={
            "serviceKey": self._api_key,
            "returnType": "json",
            "numOfRows": 100,
            "pageNo": 1,
            "sidoName": "부산",
            "ver": "1.0",
        })
        res.raise_for_status()
        response = res.json()["response"]
        if response["header"]["resultCode"] != "00":
            raise RuntimeError(f"에어코리아 API 오류: {response['header']['resultMsg']}")
        return response["body"]["items"]
