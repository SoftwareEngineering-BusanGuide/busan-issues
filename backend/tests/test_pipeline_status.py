import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.pipeline.runner import NewsPipeline
from tests.test_pipeline import NOW, FakeLlm, FakeNaver, _cls, _news

SECRETS = {
    "ncp_client_id": "ncp-id-SECRET-1",
    "ncp_client_secret": "ncp-secret-SECRET-2",
    "gemini_api_key": "gemini-SECRET-3",
    "data_go_kr_api_key": "datagokr-SECRET-4",
    "safety_data_api_key": "safety-SECRET-5",
}


@pytest.fixture
def keyed_client(tmp_path):
    # 키는 있지만 자동 수집은 끈다 (테스트에서 스케줄러가 외부 API를 부르지 않게)
    settings = Settings(_env_file=None, pipeline_enabled=False, **SECRETS)
    app = create_app(f"sqlite:///{tmp_path / 'test.db'}", settings)
    with TestClient(app) as c:
        yield c


def _assert_no_secret(res_text: str):
    for value in SECRETS.values():
        assert value not in res_text


def test_status_without_keys(client: TestClient):
    body = client.get("/api/pipeline/status").json()
    assert body["ready"] is False and body["scheduler_alive"] is False
    assert body["keys_configured"] == {k: False for k in SECRETS}
    assert body["runs"] == 0 and body["issues"] == 0 and body["articles_by_triage"] == {}


def test_status_shows_which_keys_are_set_but_never_values(keyed_client: TestClient):
    res = keyed_client.get("/api/pipeline/status")
    assert res.json()["keys_configured"] == {k: True for k in SECRETS}
    assert res.json()["ready"] is False  # 꺼 둔 상태
    _assert_no_secret(res.text)


def test_status_after_a_run(keyed_client: TestClient):
    naver = FakeNaver([_news("하단동 싱크홀 발생", "https://1", 120), _news("서울 화재", "https://2", 60)])
    llm = FakeLlm(classify={"하단동 싱크홀 발생": _cls(True, "하단동 싱크홀"), "서울 화재": _cls(False, "서울 화재")},
                  groups={"하단동 싱크홀": (None, "g")})
    pipeline = NewsPipeline(keyed_client.app.state.db, naver, llm, now=lambda: NOW)
    keyed_client.app.state.pipeline = pipeline
    pipeline.run()

    body = keyed_client.get("/api/pipeline/status").json()
    assert body["runs"] == 1 and body["running"] is False and body["stage"] is None
    assert body["last_stats"]["collected"] == 2 and body["last_stats"]["relevant"] == 1
    assert body["articles_by_triage"] == {"relevant": 1, "irrelevant": 1} and body["issues"] == 1
    assert body["last_finished_at"] >= body["last_started_at"]
    assert body["newest_article_at"] is not None


def test_errors_are_scrubbed_of_key_values(keyed_client: TestClient):
    class LeakyNaver(FakeNaver):
        def search_news(self, query, display=100, start=1):
            # 외부 라이브러리 오류에 키가 섞여 들어오는 경우를 흉내 낸다
            raise RuntimeError(f"request failed: serviceKey={SECRETS['data_go_kr_api_key']} id={SECRETS['ncp_client_id']}")

    pipeline = NewsPipeline(keyed_client.app.state.db, LeakyNaver([]), FakeLlm({}, {}), now=lambda: NOW)
    keyed_client.app.state.pipeline = pipeline
    with pytest.raises(RuntimeError):
        pipeline.run()
    pipeline.status.last_stats.errors.append(f"classify: bad key {SECRETS['gemini_api_key']}")

    res = keyed_client.get("/api/pipeline/status")
    body = res.json()
    assert body["last_error"].startswith("RuntimeError (collect 단계)") and "***" in body["last_error"]
    assert body["last_stats"]["errors"] == ["classify: bad key ***"]
    _assert_no_secret(res.text)


def test_run_status_resets_running_flag_after_failure(keyed_client: TestClient):
    class BrokenNaver(FakeNaver):
        def search_news(self, query, display=100, start=1):
            raise RuntimeError("boom")

    pipeline = NewsPipeline(keyed_client.app.state.db, BrokenNaver([]), FakeLlm({}, {}), now=lambda: NOW)
    with pytest.raises(RuntimeError):
        pipeline.run()
    assert pipeline.status.running is False and pipeline.status.runs == 1
    # 실패 뒤에도 다시 실행할 수 있어야 한다 (잠금이 풀림)
    with pytest.raises(RuntimeError):
        pipeline.run()
    assert pipeline.status.runs == 2
