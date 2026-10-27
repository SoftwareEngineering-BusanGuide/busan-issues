from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.constants import IMPORTANCE_HIGH
from app.models import Article, Issue

CITY_HALL = {"lat": 35.1798, "lng": 129.0750}

# (제목, 분류, 중요도, 위도, 경도, [기사 몇 분 전])
FIXTURE_ISSUES = [
    ("하단동 도로 싱크홀", "재난·안전", "high", 35.1066, 128.9668, [180, 120, 40]),
    ("시청 앞 중앙대로 행사 교통 통제", "교통", "high", 35.1792, 129.0763, [90, 30]),
    ("서면 상가 건물 화재", "사건·사고", "high", 35.1578, 129.0600, [70, 25]),
    ("연산교차로 도로 포장 공사", "공사·생활", "normal", 35.1856, 129.0817, [300]),
    ("거제동 일부 단수 예정", "공사·생활", "normal", 35.1890, 129.0700, [480]),
    ("장소 미상 이슈", "행정", "normal", None, None, [60]),
    ("열흘 전 서면 축제", "행사", "high", 35.1580, 129.0590, [60 * 24 * 10]),
]


@pytest.fixture
def seeded(client: TestClient) -> TestClient:
    now = datetime.now(timezone.utc)
    n = 0
    with client.app.state.db.session_factory() as session:
        for title, category, importance, lat, lng, minutes in FIXTURE_ISSUES:
            issue = Issue(title=title, category=category, importance=importance, lat=lat, lng=lng,
                          place_name=title, status_summary="요약" if len(minutes) > 1 else None,
                          updated_at=now - timedelta(minutes=min(minutes)))
            for m in minutes:
                n += 1
                issue.articles.append(Article(title=f"{title} 기사{n}", description="", url=f"https://news.test/{n}",
                                              published_at=now - timedelta(minutes=m), triage="relevant"))
            session.add(issue)
        session.commit()
    return client


def test_nearby_default_radius_is_10km(seeded: TestClient):
    res = seeded.get("/api/issues/nearby", params=CITY_HALL)
    assert res.status_code == 200
    issues = res.json()
    titles = {i["title"] for i in issues}
    assert "서면 상가 건물 화재" in titles  # 약 2.6km
    assert "하단동 도로 싱크홀" not in titles  # 약 12km
    assert all(i["distance_km"] <= 10 for i in issues)
    # 최신순
    assert [i["updated_at"] for i in issues] == sorted((i["updated_at"] for i in issues), reverse=True)


def test_nearby_whole_busan_with_max_radius(seeded: TestClient):
    titles = {i["title"] for i in seeded.get("/api/issues/nearby", params={**CITY_HALL, "radius": 50}).json()}
    assert "하단동 도로 싱크홀" in titles


def test_nearby_wider_radius_and_category(seeded: TestClient):
    narrow = seeded.get("/api/issues/nearby", params={**CITY_HALL, "radius": 2}).json()
    assert "서면 상가 건물 화재" not in {i["title"] for i in narrow}

    only_work = seeded.get("/api/issues/nearby", params={**CITY_HALL, "category": "공사·생활"}).json()
    assert only_work and all(i["category"] == "공사·생활" for i in only_work)


@pytest.mark.parametrize("params", [{"lat": 35.18}, {**CITY_HALL, "radius": 0}, {**CITY_HALL, "radius": 100}])
def test_nearby_rejects_bad_params(seeded: TestClient, params):
    assert seeded.get("/api/issues/nearby", params=params).status_code == 422


def test_top_returns_only_high_importance_latest_first(seeded: TestClient):
    issues = seeded.get("/api/issues/top").json()
    assert 1 <= len(issues) <= 5
    assert all(i["importance"] == IMPORTANCE_HIGH for i in issues)
    assert [i["updated_at"] for i in issues] == sorted((i["updated_at"] for i in issues), reverse=True)


def test_detail_has_articles_in_time_order(seeded: TestClient):
    top = seeded.get("/api/issues/top").json()
    sinkhole = next(i for i in top if i["title"] == "하단동 도로 싱크홀")
    detail = seeded.get(f"/api/issues/{sinkhole['id']}").json()
    assert detail["issue"]["status_summary"]
    published = [a["published_at"] for a in detail["articles"]]
    assert len(published) == 3 and published == sorted(published)
    assert all(a["url"].startswith("https://") for a in detail["articles"])


def test_detail_not_found(seeded: TestClient):
    assert seeded.get("/api/issues/99999").status_code == 404


def test_datetimes_include_timezone(seeded: TestClient):
    # 화면에서 'n분 전'을 정확히 계산하려면 시간대가 있어야 한다
    updated_at = seeded.get("/api/issues/top").json()[0]["updated_at"]
    assert updated_at.endswith("Z") or "+00:00" in updated_at


def test_issue_without_coordinates_is_not_nearby_but_can_be_listed(seeded: TestClient):
    wide = seeded.get("/api/issues/nearby", params={**CITY_HALL, "radius": 20}).json()
    assert "장소 미상 이슈" not in {i["title"] for i in wide}


def test_period_filter_hides_older_issues_by_default(seeded: TestClient):
    wide = {**CITY_HALL, "radius": 5}
    assert "열흘 전 서면 축제" not in {i["title"] for i in seeded.get("/api/issues/nearby", params=wide).json()}  # 기본 7일
    assert "열흘 전 서면 축제" in {i["title"] for i in seeded.get("/api/issues/nearby", params={**wide, "days": 30}).json()}
    assert "열흘 전 서면 축제" not in {i["title"] for i in seeded.get("/api/issues/top").json()}
    assert "열흘 전 서면 축제" in {i["title"] for i in seeded.get("/api/issues/top", params={"days": 30, "limit": 20}).json()}
    assert seeded.get("/api/issues/top", params={"days": 31}).status_code == 422
