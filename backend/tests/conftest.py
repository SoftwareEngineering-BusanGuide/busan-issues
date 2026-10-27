from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client(tmp_path) -> Iterator[TestClient]:
    # 테스트마다 임시 SQLite 파일을 써서 개발용 DB를 건드리지 않는다
    app = create_app(f"sqlite:///{tmp_path / 'test.db'}")
    with TestClient(app) as c:
        yield c
