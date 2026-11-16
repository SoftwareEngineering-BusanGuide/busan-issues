import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app import models  # noqa: F401  (drop_all이 테이블을 알도록 모델을 등록)
from app.db import Base, Database
from app.main import create_app


@pytest.fixture
def db_url(tmp_path) -> Iterator[str]:
    # 테스트마다 임시 SQLite 파일을 쓴다. TEST_DATABASE_URL을 주면 그 PostgreSQL에서 돌리고, 테스트마다 테이블을 비운다
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        yield f"sqlite:///{tmp_path / 'test.db'}"
        return
    engine = Database(url).engine
    Base.metadata.drop_all(engine)
    yield url
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def client(db_url) -> Iterator[TestClient]:
    # .env의 실제 API 키는 읽지 않는다 (외부 API를 호출하지 않도록)
    app = create_app(db_url, Settings(_env_file=None))
    with TestClient(app) as c:
        yield c
    app.state.db.engine.dispose()
