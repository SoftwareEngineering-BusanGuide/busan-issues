from app.config import Settings


def test_empty_env_values_fall_back_to_defaults(monkeypatch):
    # .env.example을 그대로 복사한 경우처럼 값이 비어 있어도 기본값을 써야 한다
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setenv("CORS_ORIGINS", "")
    s = Settings(_env_file=None)
    assert s.database_url.startswith("sqlite:///")
    assert s.cors_origin_list == ["http://localhost:5173"]


def test_cors_origins_split_by_comma(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:5173, http://localhost:3000")
    assert Settings(_env_file=None).cors_origin_list == ["http://localhost:5173", "http://localhost:3000"]


def test_http_client_logs_do_not_expose_api_keys():
    import logging

    import app.main  # noqa: F401  (로그 설정 적용)

    # 공공데이터 API 키가 URL에 들어가므로 httpx의 요청 로그(INFO)는 꺼져 있어야 한다
    assert not logging.getLogger("httpx").isEnabledFor(logging.INFO)
