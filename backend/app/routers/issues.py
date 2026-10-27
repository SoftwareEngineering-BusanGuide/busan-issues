from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.constants import CATEGORIES, DEFAULT_RADIUS_KM, IMPORTANCE_HIGH, MAX_RADIUS_KM
from app.db import get_session
from app.geo import distance_km
from app.models import Issue
from app.schemas import ArticleOut, IssueDetail, IssueOut, IssueSummary, NearbyIssue

router = APIRouter(prefix="/issues", tags=["issues"])

# 최근 며칠 안에 갱신된 이슈만 보여준다 (과거 4주치까지 모으므로 화면에서 기간을 고른다)
DAYS = Query(7, ge=1, le=30, description="최근 며칠 안에 갱신된 이슈")


def _since(days: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days)


@router.get("/nearby", response_model=list[NearbyIssue])
def nearby_issues(
    lat: float = Query(ge=-90, le=90),
    lng: float = Query(ge=-180, le=180),
    radius: float = Query(DEFAULT_RADIUS_KM, gt=0, le=MAX_RADIUS_KM, description="km"),
    category: str | None = Query(None, description=f"분류: {', '.join(CATEGORIES)}"),
    days: int = DAYS,
    session: Session = Depends(get_session),
) -> list[NearbyIssue]:
    """API-002 내 주변 이슈 (FR-002, FR-011). 위치는 계산에만 쓰고 저장하지 않는다 (NFR-003)."""
    stmt = select(Issue).where(Issue.lat.is_not(None), Issue.lng.is_not(None), Issue.updated_at >= _since(days))
    if category:
        stmt = stmt.where(Issue.category == category)

    # 이슈 수가 적은 동안은 거리 계산을 파이썬에서 한다. PostgreSQL 전환 시 PostGIS 등으로 옮긴다.
    result = []
    for issue in session.scalars(stmt):
        d = distance_km(lat, lng, issue.lat, issue.lng)
        if d <= radius:
            result.append(NearbyIssue(**IssueSummary.model_validate(issue).model_dump(), distance_km=round(d, 2)))
    result.sort(key=lambda i: i.updated_at, reverse=True)
    return result


@router.get("/top", response_model=list[IssueSummary])
def top_issues(
    limit: int = Query(5, ge=1, le=20),
    days: int = DAYS,
    session: Session = Depends(get_session),
) -> list[Issue]:
    """API-003 부산 주요 이슈 (FR-003). 위치와 관계없이 중요도가 높은 최신 이슈."""
    stmt = (
        select(Issue)
        .where(Issue.importance == IMPORTANCE_HIGH, Issue.updated_at >= _since(days))
        .order_by(Issue.updated_at.desc())
        .limit(limit)
    )
    return list(session.scalars(stmt))


@router.get("/{issue_id}", response_model=IssueDetail)
def issue_detail(issue_id: int, session: Session = Depends(get_session)) -> IssueDetail:
    """API-004 이슈 상세 (FR-004). 기사는 시간순이고 원문 링크를 포함한다 (NFR-004)."""
    issue = session.get(Issue, issue_id)
    if issue is None:
        raise HTTPException(status_code=404, detail="이슈를 찾을 수 없습니다.")
    return IssueDetail(
        issue=IssueOut.model_validate(issue),
        articles=[ArticleOut.model_validate(a) for a in issue.articles],
    )
