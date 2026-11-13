"""API 응답 형식 (SDD 6장)."""

from datetime import date, datetime

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class IssueSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    category: str
    importance: str
    place_name: str | None
    lat: float | None
    lng: float | None
    updated_at: datetime


class NearbyIssue(IssueSummary):
    distance_km: float


class ArticleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str
    url: str
    published_at: datetime


class IssueOut(IssueSummary):
    status_summary: str | None


class IssueDetail(BaseModel):
    issue: IssueOut
    # 시간순 (FR-005 타임라인에도 그대로 쓴다)
    articles: list[ArticleOut]


class AlertOut(BaseModel):
    id: str
    # 화면에 붙일 수신 지역 표시 (예: 부산 북구). 문자 원문(message)은 바꾸지 않는다.
    sender: str
    message: str
    issued_at: datetime
    # 수신 구·군. 비어 있으면 부산 전체
    districts: list[str]
    # 안전안내 / 긴급재난 / 위급재난
    level: str
    # 재난 유형 (예: 호우, 태풍)
    hazard: str
    source: str


class WeatherOut(BaseModel):
    """기상청 초단기실황 + 초단기예보의 하늘 상태."""

    temperature: float | None
    humidity: float | None
    precipitation_1h: float | None
    # 강수 형태 (없음, 비, 비/눈, 눈, 빗방울 ...)
    precipitation_type: str
    # 맑음 / 구름많음 / 흐림. 예보를 못 받으면 None
    sky: str | None
    wind_speed: float | None
    # 바람이 불어오는 방향 (도, 북=0 시계방향). 기상청 VEC
    wind_direction: float | None = None
    observed_at: datetime
    source: str


class DailyForecast(BaseModel):
    """하루 날씨 예보 요약 (대화형 질의에서 '내일 가도 괜찮을까?'에 답할 때 쓴다)."""

    date: date
    temp_min: float | None
    temp_max: float | None
    rain_chance: int | None  # 그날 가장 높은 강수확률 (%)
    sky: str | None  # 낮(9~18시)에 가장 많은 하늘 상태
    precipitation: str  # 낮에 가장 많은 강수 형태 (없으면 '없음')
    wind_max: float | None  # m/s


class ForecastOut(BaseModel):
    days: list[DailyForecast]
    issued_at: datetime
    source: str


class WeatherGrid(BaseModel):
    """지도 기온·바람 레이어용 부산 일대 격자 실황. 값은 [위도 행][경도 열], 바다처럼 관측이 없는 칸은 None."""

    lats: list[float]  # 남→북
    lngs: list[float]  # 서→동
    temperature: list[list[float | None]]  # ℃
    u: list[list[float | None]]  # 동서 바람 성분 (m/s, 동쪽 +)
    v: list[list[float | None]]  # 남북 바람 성분 (m/s, 북쪽 +)
    observed_at: datetime
    source: str


class AirStationOut(BaseModel):
    """지도 미세먼지 레이어용 측정소별 값."""

    station: str
    lat: float
    lng: float
    pm10: int | None
    pm25: int | None
    pm10_grade: str | None
    pm25_grade: str | None
    grade: str | None
    measured_at: datetime


class AirOut(BaseModel):
    """가장 가까운 에어코리아 측정소의 실시간 값."""

    station: str
    distance_km: float
    pm10: int | None
    pm25: int | None
    pm10_grade: str | None
    pm25_grade: str | None
    # 둘 중 나쁜 등급 (좋음 / 보통 / 나쁨 / 매우나쁨)
    grade: str | None
    measured_at: datetime
    source: str


class ChatTurnIn(BaseModel):
    role: Literal["user", "assistant"]
    text: str = Field(max_length=2000)


class ChatLocation(BaseModel):
    lat: float = Field(ge=34.5, le=36.0)
    lng: float = Field(ge=128.5, le=129.7)
    label: str = Field("기준 위치", max_length=50)


class ChatRequest(BaseModel):
    """API-006 대화형 질의. 대화 기록은 서버에 저장하지 않고 화면이 최근 몇 턴을 함께 보낸다 (NFR-003)."""

    message: str = Field(min_length=1, max_length=500)
    history: list[ChatTurnIn] = Field(default_factory=list, max_length=20)
    location: ChatLocation | None = None


class ChatResponse(BaseModel):
    # 본문의 [#id]는 issues에 있는 이슈를 가리킨다. 화면에서 눌러 지도로 이동한다
    answer: str
    issues: list[IssueSummary]
    tools_used: list[str]
