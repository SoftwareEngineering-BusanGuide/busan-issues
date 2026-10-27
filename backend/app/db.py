from collections.abc import Iterator

from fastapi import Request
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


class Database:
    """엔진과 세션 팩토리를 묶는다. 앱마다 하나씩 만들어 테스트에서 DB를 쉽게 바꿀 수 있게 한다."""

    def __init__(self, url: str):
        connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
        self.engine = create_engine(url, connect_args=connect_args)
        self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)

    def create_all(self) -> None:
        # 모델을 등록한 뒤 테이블을 만든다. 스키마가 자주 바뀌기 시작하면 Alembic 마이그레이션으로 전환한다.
        from app import models  # noqa: F401

        Base.metadata.create_all(self.engine)


def get_session(request: Request) -> Iterator[Session]:
    with request.app.state.db.session_factory() as session:
        yield session
