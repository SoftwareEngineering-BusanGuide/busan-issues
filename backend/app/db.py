from collections.abc import Iterator

from fastapi import Request
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def normalize_url(url: str) -> str:
    """Neon·Supabase 등이 주는 postgres(ql):// 주소를 psycopg(3) 드라이버 주소로 바꾼다."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix) :]
    return url


class Database:
    """엔진과 세션 팩토리를 묶는다. 앱마다 하나씩 만들어 테스트에서 DB를 쉽게 바꿀 수 있게 한다."""

    def __init__(self, url: str):
        url = normalize_url(url)
        if url.startswith("sqlite"):
            self.engine = create_engine(url, connect_args={"check_same_thread": False})
        else:
            # 무료 PostgreSQL(Neon)은 쉬는 동안 연결을 끊으므로, 쓰기 전에 연결을 확인하고 5분마다 새로 맺는다
            self.engine = create_engine(url, pool_pre_ping=True, pool_recycle=300)
        self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)

    def create_all(self) -> None:
        # 모델을 등록한 뒤 테이블을 만든다. 스키마가 자주 바뀌기 시작하면 Alembic 마이그레이션으로 전환한다.
        from app import models  # noqa: F401

        Base.metadata.create_all(self.engine)


def get_session(request: Request) -> Iterator[Session]:
    with request.app.state.db.session_factory() as session:
        yield session
