"""API 응답 형식 (SDD 6장)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class IssueSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    category: str
    importance: str
    place_name: str | None
    lat: float | None
    lng: float | None
    updated_at: datetime


class NearbyIssue(IssueSummary):
    distance_km: float


class ArticleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str
    url: str
    published_at: datetime


class IssueOut(IssueSummary):
    status_summary: str | None


class IssueDetail(BaseModel):
    issue: IssueOut
    # 시간순 (FR-005 타임라인에도 그대로 쓴다)
    articles: list[ArticleOut]


class AlertOut(BaseModel):
    id: str
    sender: str
    message: str
    issued_at: datetime
    districts: list[str]
    source: str
