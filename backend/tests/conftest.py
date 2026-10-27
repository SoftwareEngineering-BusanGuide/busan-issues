from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture
def client(tmp_path) -> Iterator[TestClient]:
    # 테스트마다 임시 SQLite 파일을 쓰고, .env의 실제 API 키는 읽지 않는다 (외부 API를 호출하지 않도록)
    app = create_app(f"sqlite:///{tmp_path / 'test.db'}", Settings(_env_file=None))
    with TestClient(app) as c:
        yield c
