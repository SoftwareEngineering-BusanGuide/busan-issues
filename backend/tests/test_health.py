from fastapi.testclient import TestClient

from app.db import Database


def test_health_ok(client: TestClient):
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok", "database": "ok"}


def test_health_reports_db_failure(client: TestClient, tmp_path, monkeypatch):
    # 존재하지 않는 폴더의 DB 파일은 연결 시점에 실패한다
    unreachable = Database(f"sqlite:///{tmp_path / 'missing' / 'x.db'}")
    monkeypatch.setattr(client.app.state.db, "session_factory", unreachable.session_factory)
    res = client.get("/api/health")
    assert res.status_code == 503
    assert res.json() == {"status": "degraded", "database": "error"}
