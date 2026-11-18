"""대화형 질의에서 LLM이 부를 수 있는 도구 (SRS FR-006, SDD API-006).

LLM은 도구 결과에 있는 사실로만 답한다. 도구는 서버 안의 함수를 바로 부르고(HTTP를 다시 거치지 않음),
결과는 LLM이 읽기 쉬운 작은 dict로 돌려준다. 실패해도 예외 대신 {"error": ...}를 돌려줘서 LLM이 '확인할 수 없다'고 답하게 한다.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.cache import DataUnavailable
from app.constants import CATEGORIES, DISTRICT_CENTERS, MAX_RADIUS_KM
from app.geo import distance_km
from app.models import Issue
from app.pipeline.geocoder import CITY_WIDE

KST = timezone(timedelta(hours=9))
MAX_ISSUES = 8
MAX_ARTICLES = 8

# Gemini functionDeclarations 형식 (OpenAPI 스키마의 일부)
_LAT = {"type": "NUMBER", "description": "위도. 생략하면 사용자의 기준 위치"}
_LNG = {"type": "NUMBER", "description": "경도. 생략하면 사용자의 기준 위치"}
DECLARATIONS: list[dict] = [
    {
        "name": "find_place",
        "description": "부산 안의 장소 이름(동네, 구·군, 해수욕장, 역, 건물 등)을 좌표로 바꾼다. 사용자가 기준 위치가 아닌 곳을 물으면 먼저 부른다.",
        "parameters": {
            "type": "OBJECT",
            "properties": {"name": {"type": "STRING", "description": "장소 이름. 예: 해운대해수욕장, 서면역, 사하구"}},
            "required": ["name"],
        },
    },
    {
        "name": "search_issues",
        "description": "뉴스로 만든 부산 지역 이슈(사고·공사·교통 통제·행사 등)를 위치·기간·분류·검색어로 찾는다. 최근 갱신된 순서.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "lat": _LAT,
                "lng": _LNG,
                "radius_km": {"type": "NUMBER", "description": f"반경 km (기본 3, 최대 {MAX_RADIUS_KM:.0f}). 부산 전체는 50"},
                "days": {"type": "INTEGER", "description": "최근 며칠 안에 갱신된 이슈 (기본: 검색어가 있으면 30, 없으면 7. 최대 30)"},
                "category": {"type": "STRING", "enum": list(CATEGORIES), "description": "분류로 좁힐 때만"},
                "keyword": {"type": "STRING", "description": "제목·요약에 들어간 말로 좁힐 때만. 예: 사직구장, 단수"},
            },
        },
    },
    {
        "name": "get_issue_timeline",
        "description": "이슈 하나의 현재 상황 요약과 관련 기사 목록(시간순, 언론사 링크)을 가져온다. 경과나 자세한 내용을 물으면 부른다.",
        "parameters": {
            "type": "OBJECT",
            "properties": {"issue_id": {"type": "INTEGER", "description": "search_issues 결과의 id"}},
            "required": ["issue_id"],
        },
    },
    {
        "name": "get_weather",
        "description": "현재 날씨(기온·강수·바람)와 오늘부터 며칠간의 날짜별 예보(최저·최고 기온, 강수확률, 하늘, 비·눈)를 가져온다.",
        "parameters": {"type": "OBJECT", "properties": {"lat": _LAT, "lng": _LNG}},
    },
    {
        "name": "get_air_quality",
        "description": "가장 가까운 측정소의 현재 미세먼지(PM10)·초미세먼지(PM2.5) 농도와 등급을 가져온다.",
        "parameters": {"type": "OBJECT", "properties": {"lat": _LAT, "lng": _LNG}},
    },
    {
        "name": "get_alerts",
        "description": "최근 부산 긴급재난문자·기상특보 원문을 가져온다. 재난·안전, 태풍·호우·폭염 등 특보를 물으면 부른다.",
        "parameters": {"type": "OBJECT", "properties": {}},
    },
]


@dataclass
class Location:
    lat: float
    lng: float
    label: str


@dataclass
class ToolBox:
    """한 번의 질문에 쓰는 도구 모음. 도구가 돌려준 이슈 id를 모아 답변의 [#id] 표시가 진짜인지 확인한다."""

    session_factory: Callable[[], Session]
    location: Location
    weather: Any = None  # KmaWeatherProvider
    air: Any = None  # AirKoreaProvider
    alerts: Any = None  # SafetyDataAlertProvider
    geocoder: Any = None  # Geocoder (네이버 지역 검색). 없으면 구·군 중심만 찾는다
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc)
    seen_issue_ids: set[int] = field(default_factory=set)
    # 타임라인까지 열어 본 이슈: 답변에 [#id]를 빠뜨려도 화면에 카드로 보여준다
    focused_issue_ids: list[int] = field(default_factory=list)

    def call(self, name: str, args: dict) -> dict:
        handler = getattr(self, f"_tool_{name}", None)
        if handler is None:
            return {"error": f"없는 도구입니다: {name}"}
        try:
            return handler(**args)
        except TypeError as e:  # LLM이 잘못된 인자를 준 경우
            return {"error": f"인자 오류: {e}"}
        except DataUnavailable:
            return {"error": "지금은 이 정보를 불러올 수 없습니다."}

    def _point(self, lat: float | None, lng: float | None) -> tuple[float, float]:
        if lat is None or lng is None:
            return self.location.lat, self.location.lng
        return float(lat), float(lng)

    def _tool_find_place(self, name: str) -> dict:
        name = name.strip()
        if name.replace(" ", "") in CITY_WIDE:
            return {"name": name, "whole_city": True, "hint": "부산 전체는 search_issues의 radius_km=50으로 찾는다"}
        district = next((d for d in sorted(DISTRICT_CENTERS, key=len, reverse=True) if name.removeprefix("부산").strip() == d), None)
        if district:
            lat, lng = DISTRICT_CENTERS[district]
            return {"name": district, "lat": lat, "lng": lng, "precision": "구·군청"}
        coords = self.geocoder.locate(name) if self.geocoder else None
        if not coords:
            return {"name": name, "found": False}
        return {"name": name, "lat": coords[0], "lng": coords[1]}

    def _tool_search_issues(
        self,
        lat: float | None = None,
        lng: float | None = None,
        radius_km: float = 3,
        days: int | None = None,
        category: str | None = None,
        keyword: str | None = None,
    ) -> dict:
        lat, lng = self._point(lat, lng)
        radius_km = min(max(float(radius_km), 0.5), MAX_RADIUS_KM)
        # 이름으로 특정 사건을 찾을 때는 지난 일일 수 있으므로 기간을 넓게 본다
        days = min(max(int(days if days is not None else (30 if keyword else 7)), 1), 30)
        stmt = select(Issue).where(
            Issue.lat.is_not(None), Issue.lng.is_not(None), Issue.updated_at >= self.now() - timedelta(days=days)
        )
        if category in CATEGORIES:
            stmt = stmt.where(Issue.category == category)
        if keyword and keyword.strip():
            pattern = f"%{keyword.strip()}%"
            stmt = stmt.where(or_(Issue.title.ilike(pattern), Issue.status_summary.ilike(pattern), Issue.place_name.ilike(pattern)))

        found = []
        with self.session_factory() as session:
            for issue in session.scalars(stmt.order_by(Issue.updated_at.desc())):
                d = distance_km(lat, lng, issue.lat, issue.lng)
                if d <= radius_km:
                    found.append((issue, d))
        self.seen_issue_ids.update(issue.id for issue, _ in found[:MAX_ISSUES])
        result: dict = {"searched": {"radius_km": radius_km, "days": days}, "total": len(found)}
        if not found:
            result["hint"] = "없으면 반경(최대 50)이나 기간(최대 30일)을 넓히거나 검색어를 줄여 다시 찾아볼 수 있다."
        return {
            **result,
            "issues": [
                {
                    "id": issue.id,
                    "title": issue.title,
                    "category": issue.category,
                    "important": issue.importance == "high",
                    "place": issue.place_name,
                    "distance_km": round(d, 1),
                    "updated_at": _kst(issue.updated_at),
                    "summary": (issue.status_summary or "")[:200] or None,
                }
                for issue, d in found[:MAX_ISSUES]
            ],
        }

    def _tool_get_issue_timeline(self, issue_id: int) -> dict:
        with self.session_factory() as session:
            issue = session.get(Issue, int(issue_id))
            if issue is None:
                return {"error": "이슈를 찾을 수 없습니다."}
            self.seen_issue_ids.add(issue.id)
            if issue.id not in self.focused_issue_ids:
                self.focused_issue_ids.append(issue.id)
            articles = issue.articles[-MAX_ARTICLES:]
            return {
                "id": issue.id,
                "title": issue.title,
                "category": issue.category,
                "place": issue.place_name,
                "summary": issue.status_summary,
                "updated_at": _kst(issue.updated_at),
                "article_count": len(issue.articles),
                "articles": [{"title": a.title, "published_at": _kst(a.published_at), "url": a.url} for a in articles],
            }

    def _tool_get_weather(self, lat: float | None = None, lng: float | None = None) -> dict:
        if self.weather is None:
            return {"error": "날씨 정보를 쓸 수 없습니다."}
        lat, lng = self._point(lat, lng)
        result: dict = {"source": "기상청"}
        try:
            now = self.weather.current(lat, lng)
            result["now"] = {
                "temperature": now.temperature, "sky": now.sky, "precipitation": now.precipitation_type,
                "precipitation_1h_mm": now.precipitation_1h, "wind_speed": now.wind_speed, "observed_at": _kst(now.observed_at),
            }
        except DataUnavailable:
            result["now"] = {"error": "현재 날씨를 불러올 수 없습니다."}
        try:
            forecast = self.weather.forecast(lat, lng)
            result["daily_forecast"] = [d.model_dump(mode="json") for d in forecast.days]
        except DataUnavailable:
            result["daily_forecast"] = {"error": "예보를 불러올 수 없습니다."}
        return result

    def _tool_get_air_quality(self, lat: float | None = None, lng: float | None = None) -> dict:
        if self.air is None:
            return {"error": "미세먼지 정보를 쓸 수 없습니다."}
        air = self.air.nearest(*self._point(lat, lng))
        return {
            "station": air.station, "distance_km": air.distance_km, "pm10": air.pm10, "pm25": air.pm25,
            "grade": air.grade, "measured_at": _kst(air.measured_at), "source": "에어코리아",
            "note": "지금 측정값이다. 내일 등 미래의 미세먼지 예보는 아니다.",
        }

    def _tool_get_alerts(self) -> dict:
        if self.alerts is None:
            return {"error": "재난문자를 쓸 수 없습니다."}
        alerts = self.alerts.list_alerts()[:5]
        return {
            "alerts": [{"sender": a.sender, "message": a.message, "issued_at": _kst(a.issued_at), "level": a.level} for a in alerts],
            "source": "행정안전부 긴급재난문자",
        }


def _kst(value: datetime) -> str:
    return value.astimezone(KST).strftime("%Y-%m-%d %H:%M")
