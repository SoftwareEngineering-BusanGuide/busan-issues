from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, HTTPException, Query, Request

from app.cache import DataUnavailable
from app.constants import DISTRICT_CENTERS
from app.schemas import AirOut, AirStationOut, DistrictWeather, WeatherOut

router = APIRouter(tags=["weather"])

LAT = Query(ge=34.5, le=36.0, description="위도 (부산 주변)")
LNG = Query(ge=128.5, le=129.7, description="경도 (부산 주변)")


@router.get("/weather", response_model=WeatherOut)
def weather(request: Request, lat: float = LAT, lng: float = LNG) -> WeatherOut:
    """기준 위치의 현재 날씨 (대화형 질의의 get_weather 도구에도 쓴다)."""
    provider = request.app.state.weather_provider
    if provider is None:
        raise HTTPException(status_code=503, detail="날씨 API 키가 설정되지 않았습니다.")
    try:
        return provider.current(lat, lng)
    except DataUnavailable:
        raise HTTPException(status_code=503, detail="날씨 정보를 일시적으로 불러올 수 없습니다.")


@router.get("/weather/districts", response_model=list[DistrictWeather])
def district_weather(request: Request) -> list[DistrictWeather]:
    """지도 날씨·바람 레이어: 16개 구·군의 현재 날씨. 한 구가 실패해도 나머지는 돌려준다."""
    provider = request.app.state.weather_provider
    if provider is None:
        raise HTTPException(status_code=503, detail="날씨 API 키가 설정되지 않았습니다.")

    def fetch(item: tuple[str, tuple[float, float]]) -> DistrictWeather | None:
        name, (lat, lng) = item
        try:
            return DistrictWeather(district=name, lat=lat, lng=lng, weather=provider.current(lat, lng))
        except DataUnavailable:
            return None

    # 구마다 기상청을 두 번씩 부르므로 동시에 요청한다 (결과는 격자별로 10분 캐시)
    with ThreadPoolExecutor(max_workers=8) as pool:
        result = [d for d in pool.map(fetch, DISTRICT_CENTERS.items()) if d]
    if not result:
        raise HTTPException(status_code=503, detail="날씨 정보를 일시적으로 불러올 수 없습니다.")
    return result


@router.get("/air/stations", response_model=list[AirStationOut])
def air_stations(request: Request) -> list[AirStationOut]:
    """지도 미세먼지 레이어: 부산 측정소별 실시간 값 (점검 중인 측정소는 뺀다)."""
    provider = request.app.state.air_provider
    if provider is None:
        raise HTTPException(status_code=503, detail="대기질 API 키가 설정되지 않았습니다.")
    try:
        return provider.stations()
    except DataUnavailable:
        raise HTTPException(status_code=503, detail="대기질 정보를 일시적으로 불러올 수 없습니다.")


@router.get("/air", response_model=AirOut)
def air(request: Request, lat: float = LAT, lng: float = LNG) -> AirOut:
    """기준 위치에서 가장 가까운 측정소의 미세먼지."""
    provider = request.app.state.air_provider
    if provider is None:
        raise HTTPException(status_code=503, detail="대기질 API 키가 설정되지 않았습니다.")
    try:
        return provider.nearest(lat, lng)
    except (DataUnavailable, LookupError):
        raise HTTPException(status_code=503, detail="대기질 정보를 일시적으로 불러올 수 없습니다.")
