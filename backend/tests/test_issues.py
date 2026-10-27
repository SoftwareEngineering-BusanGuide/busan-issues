import pytest
from fastapi.testclient import TestClient

from app.constants import IMPORTANCE_HIGH
from app.seed import seed

CITY_HALL = {"lat": 35.1798, "lng": 129.0750}


@pytest.fixture
def seeded(client: TestClient) -> TestClient:
    with client.app.state.db.session_factory() as session:
        seed(session)
    return client


def test_nearby_default_radius_is_2km(seeded: TestClient):
    res = seeded.get("/api/issues/nearby", params=CITY_HALL)
    assert res.status_code == 200
    issues = res.json()
    titles = {i["title"] for i in issues}
    assert "시청 앞 중앙대로 행사 교통 통제" in titles
    assert "서면 상가 건물 화재" not in titles  # 약 2.6km
    assert all(i["distance_km"] <= 2 for i in issues)
    # 최신순
    assert [i["updated_at"] for i in issues] == sorted((i["updated_at"] for i in issues), reverse=True)


def test_nearby_wider_radius_and_category(seeded: TestClient):
    wide = seeded.get("/api/issues/nearby", params={**CITY_HALL, "radius": 5}).json()
    assert "서면 상가 건물 화재" in {i["title"] for i in wide}

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


def test_seed_is_idempotent_unless_reset(client: TestClient):
    with client.app.state.db.session_factory() as session:
        first = seed(session)
        assert first > 0
        assert seed(session) == 0
        assert seed(session, reset=True) == first
