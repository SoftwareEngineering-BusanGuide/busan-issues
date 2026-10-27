from fastapi.testclient import TestClient


def test_alerts_latest_first_with_source(client: TestClient):
    alerts = client.get("/api/alerts").json()
    assert len(alerts) == 3
    assert [a["issued_at"] for a in alerts] == sorted((a["issued_at"] for a in alerts), reverse=True)
    assert all(a["source"] for a in alerts)  # 출처 표시 (공공누리 제4유형)


def test_alerts_filter_by_district(client: TestClient):
    alerts = client.get("/api/alerts", params={"district": "사하구"}).json()
    assert len(alerts) == 1 and "하단동" in alerts[0]["message"]
    assert client.get("/api/alerts", params={"district": "없는구"}).json() == []
