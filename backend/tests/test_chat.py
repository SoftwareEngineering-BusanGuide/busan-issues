from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.chat import Location, RateLimiter, ToolBox, answer
from app.chat.agent import build_system_prompt
from app.pipeline.llm import LlmError
from app.schemas import AirOut, DailyForecast, ForecastOut, WeatherOut
from app.weather import forecast_base_time, summarize_forecast
from tests.test_issues import seeded  # noqa: F401  (fixture)

CITY_HALL = Location(35.1798, 129.075, "부산시청")


class ScriptedLlm:
    """정해 둔 응답을 차례로 돌려주고, 받은 대화 기록을 남긴다."""

    def __init__(self, *responses: dict):
        self.responses = list(responses)
        self.calls: list[dict] = []

    def generate_with_tools(self, system, contents, tools, allow_tools=True):
        self.calls.append({"system": system, "contents": [dict(c) for c in contents], "allow_tools": allow_tools})
        return self.responses.pop(0)


def call(name: str, **args) -> dict:
    return {"role": "model", "parts": [{"functionCall": {"name": name, "args": args}, "thoughtSignature": "sig"}]}


def text(value: str) -> dict:
    return {"role": "model", "parts": [{"text": value}]}


def toolbox(client: TestClient, **kwargs) -> ToolBox:
    return ToolBox(session_factory=client.app.state.db.session_factory, location=CITY_HALL, **kwargs)


def issue_id(client: TestClient, title: str) -> int:
    issues = client.get("/api/issues/nearby", params={"lat": 35.1798, "lng": 129.075, "radius": 50, "days": 30}).json()
    return next(i["id"] for i in issues if i["title"] == title)


def test_tool_loop_runs_tools_and_keeps_only_real_issue_refs(seeded: TestClient):
    fire = issue_id(seeded, "서면 상가 건물 화재")
    llm = ScriptedLlm(
        call("search_issues", radius_km=5, category="사건·사고"),
        text(f"서면 상가 건물 화재 [#{fire}] 소식이 있어요. 없는 이슈 [#99999]\n출처: 뉴스 이슈 1건"),
    )
    result = answer(llm, toolbox(seeded), "근처에 사고 있어?", [])

    assert result.tools_used == ["search_issues"]
    assert result.issue_ids == [fire]
    assert "[#99999]" not in result.answer and f"[#{fire}]" in result.answer
    # 두 번째 호출에는 모델의 도구 호출(서명 그대로)과 도구 결과가 함께 간다
    second = llm.calls[1]["contents"]
    assert second[-2]["parts"][0]["thoughtSignature"] == "sig"
    response = second[-1]["parts"][0]["functionResponse"]
    assert response["name"] == "search_issues"
    assert [i["title"] for i in response["response"]["issues"]] == ["서면 상가 건물 화재"]


def test_issue_opened_by_timeline_is_shown_even_without_ref(seeded: TestClient):
    sinkhole = issue_id(seeded, "하단동 도로 싱크홀")
    llm = ScriptedLlm(call("get_issue_timeline", issue_id=sinkhole), text("복구 중입니다."))
    assert answer(llm, toolbox(seeded), "싱크홀 어떻게 됐어?", []).issue_ids == [sinkhole]


def test_history_is_sent_as_model_and_user_turns(seeded: TestClient):
    from app.chat import ChatTurn

    llm = ScriptedLlm(text("네"))
    answer(llm, toolbox(seeded), "그럼 내일은?", [ChatTurn("user", "오늘 날씨?"), ChatTurn("assistant", "맑아요")])
    assert [c["role"] for c in llm.calls[0]["contents"]] == ["user", "model", "user"]


def test_last_round_forbids_tools_so_it_must_answer(seeded: TestClient):
    llm = ScriptedLlm(*[call("get_alerts")] * 5, text("확인한 재난문자가 없습니다."))
    result = answer(llm, toolbox(seeded), "재난문자 있어?", [])
    assert [c["allow_tools"] for c in llm.calls] == [True] * 5 + [False]
    assert result.answer == "확인한 재난문자가 없습니다."


def test_search_by_keyword_place_and_days(seeded: TestClient):
    box = toolbox(seeded)
    assert [i["title"] for i in box.call("search_issues", {"keyword": "단수"})["issues"]] == ["거제동 일부 단수 예정"]
    # 하단동은 시청에서 약 12km: 좌표를 주면 그 주변에서 찾는다
    hadan = box.call("search_issues", {"lat": 35.1066, "lng": 128.9668, "radius_km": 2})
    assert [i["title"] for i in hadan["issues"]] == ["하단동 도로 싱크홀"]
    assert "열흘 전 서면 축제" not in {i["title"] for i in box.call("search_issues", {"radius_km": 50})["issues"]}
    assert "열흘 전 서면 축제" in {i["title"] for i in box.call("search_issues", {"radius_km": 50, "days": 30})["issues"]}
    # 이름으로 찾을 때는 기본 30일을 본다. 못 찾으면 넓혀 보라는 안내를 붙인다
    assert [i["title"] for i in box.call("search_issues", {"keyword": "서면 축제"})["issues"]] == ["열흘 전 서면 축제"]
    assert "hint" in box.call("search_issues", {"keyword": "없는 사건"})


def test_timeline_and_bad_calls(seeded: TestClient):
    box = toolbox(seeded)
    timeline = box.call("get_issue_timeline", {"issue_id": issue_id(seeded, "하단동 도로 싱크홀")})
    assert timeline["article_count"] == 3 and len(timeline["articles"]) == 3
    assert box.call("get_issue_timeline", {"issue_id": 99999}) == {"error": "이슈를 찾을 수 없습니다."}
    assert "error" in box.call("search_issues", {"nope": 1})
    assert "error" in box.call("delete_everything", {})
    # 키가 없는 정보는 오류로 알려 LLM이 '확인할 수 없다'고 답하게 한다
    assert "error" in box.call("get_weather", {}) and "error" in box.call("get_alerts", {})


def test_find_place_uses_district_then_geocoder(seeded: TestClient):
    class FakeGeocoder:
        def locate(self, place):
            return (35.1587, 129.1604) if place == "해운대해수욕장" else None

    box = toolbox(seeded, geocoder=FakeGeocoder())
    assert box.call("find_place", {"name": "사하구"})["lat"] == pytest.approx(35.1046)
    assert box.call("find_place", {"name": "해운대해수욕장"}) == {"name": "해운대해수욕장", "lat": 35.1587, "lng": 129.1604}
    assert box.call("find_place", {"name": "없는곳"})["found"] is False
    assert box.call("find_place", {"name": "부산"})["whole_city"] is True


def test_weather_and_air_tools_use_providers(seeded: TestClient):
    now = datetime(2026, 11, 13, 12, tzinfo=timezone.utc)

    class FakeWeather:
        def current(self, lat, lng):
            return WeatherOut(temperature=15, humidity=60, precipitation_1h=0, precipitation_type="없음", sky="맑음",
                              wind_speed=2, observed_at=now, source="기상청")

        def forecast(self, lat, lng):
            day = DailyForecast(date=date(2026, 11, 14), temp_min=14, temp_max=17, rain_chance=60, sky="흐림",
                                precipitation="비", wind_max=2.7)
            return ForecastOut(days=[day], issued_at=now, source="기상청")

    class FakeAir:
        def nearest(self, lat, lng):
            return AirOut(station="전포동", distance_km=2.9, pm10=41, pm25=27, pm10_grade="보통", pm25_grade="보통",
                          grade="보통", measured_at=now, source="에어코리아")

    box = toolbox(seeded, weather=FakeWeather(), air=FakeAir())
    weather = box.call("get_weather", {})
    assert weather["now"]["temperature"] == 15
    assert weather["daily_forecast"][0] == {"date": "2026-11-14", "temp_min": 14, "temp_max": 17, "rain_chance": 60,
                                            "sky": "흐림", "precipitation": "비", "wind_max": 2.7}
    assert box.call("get_air_quality", {})["grade"] == "보통"


def test_system_prompt_has_korean_time_and_location(seeded: TestClient):
    prompt = build_system_prompt(toolbox(seeded), datetime(2026, 11, 13, 13, 5, tzinfo=timezone.utc))
    assert "2026-11-13 (금) 22:05" in prompt and "부산시청" in prompt


def test_rate_limiter():
    clock = [0.0]
    limiter = RateLimiter(per_minute=2, per_day=3, total_per_day=4, clock=lambda: clock[0])
    assert limiter.check("a") is None and limiter.check("a") is None
    assert "잦습니다" in limiter.check("a")
    clock[0] = 61
    assert limiter.check("a") is None
    assert "횟수" in limiter.check("a")  # 하루 3번
    assert limiter.check("b") is None
    assert "내일" in limiter.check("c")  # 서비스 전체 하루 4번
    clock[0] = 61 + 86400
    assert limiter.check("a") is None


def test_forecast_summary_and_base_time():
    kst = timezone.utc  # 아래 시각은 UTC로 주고 결과는 한국 시간으로 본다
    assert forecast_base_time(datetime(2026, 11, 13, 5, 9, tzinfo=kst)).hour == 11  # 14:09 KST → 11시 발표
    assert forecast_base_time(datetime(2026, 11, 13, 5, 11, tzinfo=kst)).hour == 14  # 14:11 KST → 14시 발표
    assert forecast_base_time(datetime(2026, 11, 12, 17, 0, tzinfo=kst)).day == 12  # 02:00 KST → 전날 23시
    items = [
        {"fcstDate": "20261114", "fcstTime": "0600", "category": "TMN", "fcstValue": "14.0"},
        {"fcstDate": "20261114", "fcstTime": "1500", "category": "TMX", "fcstValue": "17.0"},
        {"fcstDate": "20261114", "fcstTime": "1200", "category": "POP", "fcstValue": "60"},
        {"fcstDate": "20261114", "fcstTime": "1200", "category": "SKY", "fcstValue": "4"},
        {"fcstDate": "20261114", "fcstTime": "1300", "category": "SKY", "fcstValue": "4"},
        {"fcstDate": "20261114", "fcstTime": "0300", "category": "SKY", "fcstValue": "1"},  # 밤은 빼고 본다
        {"fcstDate": "20261114", "fcstTime": "1200", "category": "PTY", "fcstValue": "1"},
        {"fcstDate": "20261114", "fcstTime": "1200", "category": "WSD", "fcstValue": "2.7"},
    ]
    [day] = summarize_forecast(items)
    assert (day.temp_min, day.temp_max, day.rain_chance, day.sky, day.precipitation, day.wind_max) == (14, 17, 60, "흐림", "비", 2.7)


def test_endpoint_without_key_returns_503(client: TestClient):
    assert client.post("/api/chat", json={"message": "안녕"}).status_code == 503


def test_endpoint_answers_with_issue_cards(seeded: TestClient):
    fire = issue_id(seeded, "서면 상가 건물 화재")
    seeded.app.state.chat_llm = ScriptedLlm(call("search_issues", radius_km=5), text(f"화재 소식 [#{fire}]"))
    res = seeded.post("/api/chat", json={"message": "근처 사고?", "location": {"lat": 35.1798, "lng": 129.075, "label": "시청"}})
    assert res.status_code == 200
    body = res.json()
    assert body["answer"] == f"화재 소식 [#{fire}]" and body["tools_used"] == ["search_issues"]
    assert [i["title"] for i in body["issues"]] == ["서면 상가 건물 화재"]


def test_endpoint_validates_limits_and_llm_errors(seeded: TestClient):
    class Broken:
        def generate_with_tools(self, *args, **kwargs):
            raise LlmError("Gemini 오류 500")

    seeded.app.state.chat_llm = Broken()
    assert seeded.post("/api/chat", json={"message": ""}).status_code == 422
    assert seeded.post("/api/chat", json={"message": "x" * 501}).status_code == 422
    assert seeded.post("/api/chat", json={"message": "hi", "location": {"lat": 37.5, "lng": 127.0}}).status_code == 422
    assert seeded.post("/api/chat", json={"message": "hi"}).status_code == 502

    seeded.app.state.chat_limiter = RateLimiter(per_minute=1, per_day=10, total_per_day=10)
    headers = {"x-forwarded-for": "1.2.3.4, 10.0.0.1"}
    seeded.post("/api/chat", json={"message": "hi"}, headers=headers)
    assert seeded.post("/api/chat", json={"message": "hi"}, headers=headers).status_code == 429
    assert seeded.post("/api/chat", json={"message": "hi"}, headers={"x-forwarded-for": "5.6.7.8"}).status_code == 502
