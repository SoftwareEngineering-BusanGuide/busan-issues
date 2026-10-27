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
