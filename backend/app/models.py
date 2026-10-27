"""SDD 5.2 테이블 정의."""

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

from app.db import Base


class UTCDateTime(TypeDecorator):
    """UTC로 저장하고, 시간대를 저장하지 않는 SQLite에서 읽을 때도 UTC 시각으로 돌려준다."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect) -> datetime | None:
        if value is not None and value.tzinfo is not None:
            value = value.astimezone(timezone.utc)
        return value

    def process_result_value(self, value: datetime | None, dialect) -> datetime | None:
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value


class Issue(Base):
    """같은 사건을 다룬 기사들을 묶은 이슈 (FR-002 ~ FR-005, FR-010)."""

    __tablename__ = "issues"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(300))
    # 분류 결과 (FR-011, AI-REQ-01)
    category: Mapped[str] = mapped_column(String(50), index=True)
    # 부산 주요 이슈 여부 판단에 쓰는 중요도 (FR-003)
    importance: Mapped[str] = mapped_column(String(20), index=True)
    # 타임라인의 현재 상황 요약 (FR-005, AI-REQ-03)
    status_summary: Mapped[str | None] = mapped_column(Text)
    # 장소 추출·지오코딩 결과 (FR-002, AI-REQ-02). 실패하면 비워 둔다.
    place_name: Mapped[str | None] = mapped_column(String(200))
    lat: Mapped[float | None] = mapped_column(Numeric(9, 6, asdecimal=False))
    lng: Mapped[float | None] = mapped_column(Numeric(9, 6, asdecimal=False))
    # 마지막 기사 반영 시각 (FR-005)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True)

    articles: Mapped[list["Article"]] = relationship(back_populates="issue", order_by="Article.published_at")


class Article(Base):
    """수집한 뉴스 기사. 본문은 저장하지 않고 제목·검색 API 요약·원문 링크만 둔다 (FR-004, NFR-004)."""

    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(primary_key=True)
    # 아직 이슈로 묶이지 않은 기사는 비어 있다 (FR-010)
    issue_id: Mapped[int | None] = mapped_column(ForeignKey("issues.id"), index=True)
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text)
    # 같은 기사를 두 번 수집하지 않도록 원문 링크를 고유하게 둔다 (FR-008)
    url: Mapped[str] = mapped_column(String(1000), unique=True)
    published_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True)

    issue: Mapped[Issue | None] = relationship(back_populates="articles")
