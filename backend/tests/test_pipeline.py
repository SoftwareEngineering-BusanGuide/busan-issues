import json
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models import Article, Issue
from app.pipeline import analyzer
from app.pipeline.collector import collect_news
from app.pipeline.geocoder import Geocoder
from app.pipeline.llm import GeminiClient, LlmError
from app.pipeline.naver import clean_text
from app.pipeline.runner import NewsPipeline

NOW = datetime(2026, 10, 27, 6, 0, tzinfo=timezone.utc)


def _news(title: str, url: str, minutes_ago: int, desc: str = "요약") -> dict:
    return {"title": f"<b>{title}</b>", "description": desc, "originallink": url, "link": url + "?naver",
            "pubDate": format_datetime(NOW - timedelta(minutes=minutes_ago))}


class FakeNaver:
    def __init__(self, news: list[dict], places: dict[str, tuple[float, float, str]] | None = None):
        self.news = news
        self.places = places or {}
        self.local_queries: list[str] = []

    def search_news(self, query: str, display: int = 100, start: int = 1) -> list[dict]:
        return self.news if query == "부산" else self.news[:1]  # 다른 검색어에서도 같은 기사가 겹쳐 나온다

    def search_local(self, query: str, display: int = 5) -> list[dict]:
        self.local_queries.append(query)
        for key, (lat, lng, address) in self.places.items():
            if key in query:
                return [{"title": key, "address": address, "roadAddress": "", "mapx": str(int(lng * 1e7)),
                         "mapy": str(int(lat * 1e7))}]
        return []


class FakeLlm:
    """프롬프트 안의 JSON을 읽어, 기사 제목별로 정해 둔 답을 돌려준다."""

    def __init__(self, classify: dict[str, dict], groups: dict[str, tuple[str | None, str]], fail: set[str] = frozenset()):
        self.classify = classify
        self.groups = groups  # 이슈 제목 → (기존 이슈 제목 또는 None, 그룹 이름)
        self.fail = fail
        self.calls: list[str] = []

    def generate_json(self, prompt: str, schema: dict):
        if schema is analyzer.CLASSIFY_SCHEMA:
            self.calls.append("classify")
            if "classify" in self.fail:
                raise LlmError("down")
            rows = json.loads(prompt.split("기사:\n", 1)[1])
            return [{"id": r["id"], **self.classify[r["title"]]} for r in rows if r["title"] in self.classify]
        if schema is analyzer.GROUP_SCHEMA:
            self.calls.append("group")
            existing = {i["title"]: i["issue_id"] for i in json.loads(prompt.split("기존 이슈:\n", 1)[1].split("\n\n새 기사:")[0])}
            rows = json.loads(prompt.split("새 기사:\n", 1)[1])
            out = []
            for r in rows:
                target, group = self.groups[r["title"]]
                out.append({"id": r["id"], "issue_id": existing.get(target) if target else None, "group": group})
            return out
        self.calls.append("summary")
        return {"summary": "도로 침하로 통제 중이며 복구 작업이 진행되고 있다."}


def _cls(busan: bool, title: str, place: str | None = None, category: str = "재난·안전", importance: str = "normal"):
    return {"busan_issue": busan, "category": category, "importance": importance, "place": place, "title": title}


@pytest.fixture
def db(client: TestClient):
    return client.app.state.db


def test_clean_text():
    assert clean_text("<b>부산</b> &quot;싱크홀&quot; &amp; 통제") == '부산 "싱크홀" & 통제'


def test_collect_dedupes_skips_old_and_existing(db):
    naver = FakeNaver([_news("A", "https://a", 10), _news("B", "https://b", 60 * 30), _news("C", "https://c", 5)])
    with db.session_factory() as session:
        session.add(Article(title="C", description="", url="https://c", published_at=NOW, triage="relevant"))
        session.commit()
        assert collect_news(session, naver, NOW) == 1  # A만 새 기사 (B는 30시간 전, C는 이미 있음)
        a = session.scalars(select(Article).where(Article.url == "https://a")).one()
        assert a.title == "A" and a.triage == "pending"


def test_full_run_groups_filters_geocodes_and_summarizes(db):
    naver = FakeNaver(
        [_news("하단동 싱크홀 발생", "https://1", 120), _news("싱크홀 구간 통제", "https://2", 60),
         _news("서울 화재", "https://3", 50), _news("구청 정책 발표", "https://4", 30)],
        places={"하단동": (35.1066, 128.9668, "부산광역시 사하구 하단동")},
    )
    llm = FakeLlm(
        classify={
            "하단동 싱크홀 발생": _cls(True, "하단동 도로 싱크홀", "사하구 하단동", importance="high"),
            "싱크홀 구간 통제": _cls(True, "싱크홀 구간 차로 통제", "사하구 하단동"),
            "서울 화재": _cls(False, "서울 화재", category="사건·사고"),
            "구청 정책 발표": _cls(True, "구청 정책 발표", "수영구 어딘가", category="행정"),
        },
        groups={"하단동 도로 싱크홀": (None, "sinkhole"), "싱크홀 구간 차로 통제": (None, "sinkhole"),
                "구청 정책 발표": (None, "policy")},
    )
    stats = NewsPipeline(db, naver, llm, now=lambda: NOW).run()
    assert (stats.collected, stats.relevant, stats.issues_created, stats.summarized) == (4, 3, 2, 1)

    with db.session_factory() as session:
        issues = {i.title: i for i in session.scalars(select(Issue))}
        sinkhole = issues["하단동 도로 싱크홀"]  # 첫 기사의 제목이 이슈 제목
        assert [a.title for a in sinkhole.articles] == ["하단동 싱크홀 발생", "싱크홀 구간 통제"]
        assert (sinkhole.lat, sinkhole.lng) == (35.1066, 128.9668)
        assert sinkhole.importance == "high" and sinkhole.status_summary
        # 지역 검색에서 못 찾으면 구·군청 좌표
        policy = issues["구청 정책 발표"]
        assert (policy.lat, policy.lng) == (35.1455, 129.1131)
        # 부산 무관 기사는 이슈가 되지 않는다
        seoul = session.scalars(select(Article).where(Article.url == "https://3")).one()
        assert seoul.triage == "irrelevant" and seoul.issue_id is None


def test_second_run_attaches_new_article_to_existing_issue(db):
    naver = FakeNaver([_news("하단동 싱크홀 발생", "https://1", 120)], places={"하단동": (35.1066, 128.9668, "부산 사하구")})
    llm = FakeLlm(classify={"하단동 싱크홀 발생": _cls(True, "하단동 도로 싱크홀", "사하구 하단동")},
                  groups={"하단동 도로 싱크홀": (None, "sinkhole")})
    NewsPipeline(db, naver, llm, now=lambda: NOW).run()

    naver.news = [_news("싱크홀 복구 착수", "https://5", 10)]
    llm.classify["싱크홀 복구 착수"] = _cls(True, "싱크홀 복구 착수", "사하구 하단동", importance="high")
    llm.groups["싱크홀 복구 착수"] = ("하단동 도로 싱크홀", "x")
    stats = NewsPipeline(db, naver, llm, now=lambda: NOW).run()
    assert (stats.issues_created, stats.issues_updated) == (0, 1)

    with db.session_factory() as session:
        issue = session.scalars(select(Issue)).one()
        assert len(issue.articles) == 2 and issue.importance == "high"
        assert issue.updated_at == NOW - timedelta(minutes=10)


def test_llm_failure_keeps_articles_pending_for_next_run(db):
    naver = FakeNaver([_news("하단동 싱크홀 발생", "https://1", 120)])
    llm = FakeLlm(classify={}, groups={}, fail={"classify"})
    stats = NewsPipeline(db, naver, llm, now=lambda: NOW).run()
    assert stats.relevant == 0 and stats.errors
    with db.session_factory() as session:
        assert session.scalars(select(Article)).one().triage == "pending"
        assert session.scalars(select(Issue)).first() is None


def test_grouping_failure_falls_back_to_one_issue_per_article(db):
    naver = FakeNaver([_news("A", "https://1", 20), _news("B", "https://2", 10)])
    llm = FakeLlm(classify={"A": _cls(True, "A"), "B": _cls(True, "B")}, groups={})  # groups에 없으면 KeyError
    llm.generate_json_orig = llm.generate_json

    def flaky(prompt, schema):
        if schema is analyzer.GROUP_SCHEMA:
            raise LlmError("down")
        return llm.generate_json_orig(prompt, schema)

    llm.generate_json = flaky
    stats = NewsPipeline(db, naver, llm, now=lambda: NOW).run()
    assert stats.issues_created == 2 and stats.errors


def test_geocoder_rejects_results_outside_busan():
    naver = FakeNaver([], places={"해운대": (37.5, 127.0, "서울특별시 해운대 식당")})
    assert Geocoder(naver).locate("해운대 어딘가") is None
    assert Geocoder(naver).locate("강서구 대저동") == (35.2122, 128.9806)  # '서구'가 아니라 '강서구'


def test_geocoder_does_not_pin_city_wide_places():
    naver = FakeNaver([], places={"부산": (35.1798, 129.075, "부산광역시 연제구")})
    assert Geocoder(naver).locate("부산시") is None and Geocoder(naver).locate("부산 광역시") is None
    assert naver.local_queries == []  # 검색도 하지 않는다


def test_gemini_client_retries_rate_limit_then_parses_json():
    responses = iter([httpx.Response(429), httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": '{"a": 1}'}]}}]})])
    client = httpx.Client(transport=httpx.MockTransport(lambda request: next(responses)))
    sleeps = []
    llm = GeminiClient("k", "m", client=client, sleep=sleeps.append)
    assert llm.generate_json("p", {}) == {"a": 1} and sleeps == [5]


def test_gemini_client_raises_on_bad_request():
    client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(400, text="bad")))
    with pytest.raises(LlmError):
        GeminiClient("k", "m", client=client, sleep=lambda s: None).generate_json("p", {})
