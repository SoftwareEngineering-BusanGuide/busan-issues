"""기상청 단기예보 조회서비스: 초단기실황(현재 기온 등) + 초단기예보(하늘 상태)."""

import math
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import httpx

from app.cache import DataUnavailable, StaleCache
from app.schemas import WeatherGrid, WeatherOut

KST = timezone(timedelta(hours=9))
KMA_URL = "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0"
SOURCE = "기상청 단기예보 조회서비스 (공공데이터포털)"

PRECIPITATION_TYPES = {"0": "없음", "1": "비", "2": "비/눈", "3": "눈", "5": "빗방울", "6": "빗방울/눈날림", "7": "눈날림"}
SKY_TYPES = {"1": "맑음", "3": "구름많음", "4": "흐림"}

# 지도 기온·바람 레이어용 격자 (약 8km 간격, 부산 전역과 주변 바다). 기상청 셀 72개.
GRID_LATS = [round(34.90 + i * 0.075, 3) for i in range(8)]  # 34.90 ~ 35.425
GRID_LNGS = [round(128.72 + j * 0.075, 3) for j in range(9)]  # 128.72 ~ 129.32
MISSING_BELOW = -900  # 기상청 결측값(-999, -998.9). 바다 셀은 실황이 없다


def to_grid(lat: float, lng: float) -> tuple[int, int]:
    """위경도 → 기상청 격자(nx, ny). 기상청 활용가이드의 LCC 투영 공식."""
    re_km, grid_km = 6371.00877, 5.0
    slat1, slat2, olon, olat, xo, yo = 30.0, 60.0, 126.0, 38.0, 43, 136
    d = math.pi / 180.0
    re = re_km / grid_km
    slat1, slat2, olon, olat = slat1 * d, slat2 * d, olon * d, olat * d
    sn = math.log(math.cos(slat1) / math.cos(slat2)) / math.log(
        math.tan(math.pi * 0.25 + slat2 * 0.5) / math.tan(math.pi * 0.25 + slat1 * 0.5)
    )
    sf = math.tan(math.pi * 0.25 + slat1 * 0.5) ** sn * math.cos(slat1) / sn
    ro = re * sf / math.tan(math.pi * 0.25 + olat * 0.5) ** sn
    ra = re * sf / math.tan(math.pi * 0.25 + lat * d * 0.5) ** sn
    theta = lng * d - olon
    theta = (theta + math.pi) % (2 * math.pi) - math.pi
    theta *= sn
    return int(ra * math.sin(theta) + xo + 0.5), int(ro - ra * math.cos(theta) + yo + 0.5)


def base_times(now: datetime) -> tuple[datetime, datetime]:
    """(초단기실황 발표 시각, 초단기예보 발표 시각).

    실황은 매시 정각 자료가 약 40분 뒤, 초단기예보는 매시 30분 자료가 약 45분 뒤에 나온다.
    """
    now = now.astimezone(KST)
    ncst = (now - timedelta(minutes=40)).replace(minute=0, second=0, microsecond=0)
    fcst = (now - timedelta(minutes=45)).replace(minute=30, second=0, microsecond=0)
    if fcst > now - timedelta(minutes=45):
        fcst -= timedelta(hours=1)
    return ncst, fcst


def _number(value: object) -> float | None:
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


def _observed(value: object) -> float | None:
    number = _number(value)
    return None if number is None or number < MISSING_BELOW else number


class KmaWeatherProvider:
    def __init__(self, api_key: str, client: httpx.Client | None = None):
        self._api_key = api_key
        self._client = client or httpx.Client(timeout=10)
        # 실황은 한 시간에 한 번 바뀌므로 격자별로 10분 캐시
        self._cache: StaleCache[WeatherOut] = StaleCache(ttl_seconds=600)
        # 격자 전체는 발표 시각(매시)마다 한 번만 받는다. 새 시각 자료를 못 받으면 직전 격자를 쓴다
        self._grid_cache: StaleCache[WeatherGrid] = StaleCache(ttl_seconds=3600)
        self._last_grid: WeatherGrid | None = None

    def grid(self) -> WeatherGrid:
        """부산 일대 격자의 기온과 바람 성분 (지도 레이어용)."""
        base, _ = base_times(datetime.now(KST))
        try:
            grid = self._grid_cache.get(base.isoformat(), lambda: self._fetch_grid(base))
        except DataUnavailable:
            if self._last_grid is None:
                raise
            return self._last_grid
        self._last_grid = grid
        return grid

    def _fetch_grid(self, base: datetime) -> WeatherGrid:
        points = [(lat, lng) for lat in GRID_LATS for lng in GRID_LNGS]

        def fetch(point: tuple[float, float]) -> dict | None:
            nx, ny = to_grid(*point)
            try:
                return {i["category"]: i["obsrValue"] for i in self._items("getUltraSrtNcst", base, nx, ny)}
            except (httpx.HTTPError, KeyError, RuntimeError, ValueError):
                return None

        # 72칸을 동시에 받는다 (약 1초)
        with ThreadPoolExecutor(max_workers=8) as pool:
            observations = list(pool.map(fetch, points))
        if sum(1 for o in observations if o and _observed(o.get("T1H")) is not None) < 5:
            raise RuntimeError("기상청 격자 실황을 충분히 받지 못했습니다.")

        def field(key: str) -> list[list[float | None]]:
            values = [_observed(o.get(key)) if o else None for o in observations]
            return [values[r * len(GRID_LNGS) : (r + 1) * len(GRID_LNGS)] for r in range(len(GRID_LATS))]

        return WeatherGrid(
            lats=GRID_LATS, lngs=GRID_LNGS, temperature=field("T1H"), u=field("UUU"), v=field("VVV"),
            observed_at=base, source=SOURCE,
        )

    def current(self, lat: float, lng: float) -> WeatherOut:
        nx, ny = to_grid(lat, lng)
        return self._cache.get((nx, ny), lambda: self._fetch(nx, ny))

    def _items(self, operation: str, base: datetime, nx: int, ny: int) -> list[dict]:
        res = self._client.get(f"{KMA_URL}/{operation}", params={
            "serviceKey": self._api_key,
            "dataType": "JSON",
            "pageNo": 1,
            "numOfRows": 100,
            "base_date": base.strftime("%Y%m%d"),
            "base_time": base.strftime("%H%M"),
            "nx": nx,
            "ny": ny,
        })
        res.raise_for_status()
        response = res.json()["response"]
        if response["header"]["resultCode"] != "00":
            raise RuntimeError(f"기상청 API 오류: {response['header']['resultMsg']}")
        return response["body"]["items"]["item"]

    def _fetch(self, nx: int, ny: int) -> WeatherOut:
        ncst_base, fcst_base = base_times(datetime.now(KST))
        obs = {i["category"]: i["obsrValue"] for i in self._items("getUltraSrtNcst", ncst_base, nx, ny)}

        # 하늘 상태는 실황에 없어서 초단기예보의 가장 가까운 시각 값을 쓴다. 실패해도 나머지는 보여준다.
        sky = None
        try:
            forecasts = sorted(
                (i for i in self._items("getUltraSrtFcst", fcst_base, nx, ny) if i["category"] == "SKY"),
                key=lambda i: (i["fcstDate"], i["fcstTime"]),
            )
            if forecasts:
                sky = SKY_TYPES.get(str(forecasts[0]["fcstValue"]))
        except (httpx.HTTPError, KeyError, RuntimeError, ValueError):
            pass

        return WeatherOut(
            temperature=_number(obs.get("T1H")),
            humidity=_number(obs.get("REH")),
            precipitation_1h=_number(obs.get("RN1")),
            precipitation_type=PRECIPITATION_TYPES.get(str(obs.get("PTY")), "없음"),
            sky=sky,
            wind_speed=_number(obs.get("WSD")),
            wind_direction=_number(obs.get("VEC")),
            observed_at=ncst_base,
            source=SOURCE,
        )
