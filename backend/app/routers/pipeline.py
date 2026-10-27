"""뉴스 수집 파이프라인 상태 확인. 배포 서버에서 수집이 도는지, 어디서 막혔는지 로그 없이 보기 위한 용도다.

키 값은 절대 내보내지 않는다: 키는 '설정됐는지 여부'만 보여주고, 오류 메시지에 키가 섞여 있으면 가린다.
"""

from dataclasses import asdict
from datetime import datetime

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import get_session
from app.models import Article, Issue

router = APIRouter(prefix="/pipeline", tags=["pipeline"])

SECRET_FIELDS = ("ncp_client_id", "ncp_client_secret", "gemini_api_key", "data_go_kr_api_key", "safety_data_api_key")


class LastStats(BaseModel):
    collected: int
    classified: int
    relevant: int
    issues_created: int
    issues_updated: int
    summarized: int
    errors: list[str]


class PipelineStatus(BaseModel):
    enabled: bool
    # 키별 설정 여부 (값은 내보내지 않는다)
    keys_configured: dict[str, bool]
    # 수집에 필요한 키가 모두 있고 켜져 있는지. False면 서버가 수집을 시작하지 않는다
    ready: bool
    scheduler_alive: bool
    interval_minutes: int
    news_max_age_days: int
    max_per_run: int
    gemini_model: str
    server_started_at: datetime
    runs: int
    running: bool
    stage: str | None
    last_started_at: datetime | None
    last_finished_at: datetime | None
    last_stats: LastStats | None
    last_error: str | None
    articles_by_triage: dict[str, int]
    issues: int
    oldest_article_at: datetime | None
    newest_article_at: datetime | None


def scrub(text: str, settings: Settings) -> str:
    """오류 메시지에 키 값이 들어 있으면 ***로 가린다."""
    for field in SECRET_FIELDS:
        value = getattr(settings, field)
        if value and len(value) >= 4:
            text = text.replace(value, "***")
    return text[:500]


@router.get("/status", response_model=PipelineStatus)
def pipeline_status(request: Request, session: Session = Depends(get_session)) -> PipelineStatus:
    state = request.app.state
    cfg: Settings = state.settings
    pipeline = state.pipeline
    scheduler = state.scheduler
    status = pipeline.status if pipeline else None

    last_stats = None
    if status and status.last_stats:
        raw = asdict(status.last_stats)
        raw["errors"] = [scrub(e, cfg) for e in raw["errors"][-10:]]
        last_stats = LastStats(**raw)

    oldest, newest = session.execute(select(func.min(Article.published_at), func.max(Article.published_at))).one()
    return PipelineStatus(
        enabled=cfg.pipeline_enabled,
        keys_configured={field: bool(getattr(cfg, field)) for field in SECRET_FIELDS},
        ready=cfg.pipeline_ready,
        scheduler_alive=bool(scheduler and scheduler.alive),
        interval_minutes=cfg.pipeline_interval_minutes,
        news_max_age_days=cfg.news_max_age_days,
        max_per_run=cfg.pipeline_max_per_run,
        gemini_model=cfg.gemini_model,
        server_started_at=state.started_at,
        runs=status.runs if status else 0,
        running=status.running if status else False,
        stage=status.stage if status else None,
        last_started_at=status.last_started_at if status else None,
        last_finished_at=status.last_finished_at if status else None,
        last_stats=last_stats,
        last_error=scrub(status.last_error, cfg) if status and status.last_error else None,
        articles_by_triage=dict(session.execute(select(Article.triage, func.count()).group_by(Article.triage)).all()),
        issues=session.scalar(select(func.count()).select_from(Issue)) or 0,
        oldest_article_at=oldest,
        newest_article_at=newest,
    )
