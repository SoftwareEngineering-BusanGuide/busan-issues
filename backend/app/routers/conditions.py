from fastapi import APIRouter, HTTPException, Query, Request

from app.cache import DataUnavailable
from app.schemas import AirOut, AirStationOut, WeatherGrid, WeatherOut

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


@router.get("/weather/grid", response_model=WeatherGrid)
def weather_grid(request: Request) -> WeatherGrid:
    """지도 기온·바람 레이어: 부산 일대 약 8km 격자의 기온과 바람 성분 (매시 갱신)."""
    provider = request.app.state.weather_provider
    if provider is None:
        raise HTTPException(status_code=503, detail="날씨 API 키가 설정되지 않았습니다.")
    try:
        return provider.grid()
    except DataUnavailable:
        raise HTTPException(status_code=503, detail="날씨 정보를 일시적으로 불러올 수 없습니다.")


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
