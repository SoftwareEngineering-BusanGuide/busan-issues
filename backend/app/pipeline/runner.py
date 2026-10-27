"""뉴스 수집 파이프라인 실행: 수집 → 판별·분류 → 같은 사건 묶기 → 좌표 변환 → 상황 요약 (SDD ADR-003)."""

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.constants import IMPORTANCE_HIGH
from app.db import Database
from app.models import Article, Issue
from app.pipeline import analyzer
from app.pipeline.collector import collect_news
from app.pipeline.geocoder import Geocoder
from app.pipeline.llm import GeminiClient, LlmError
from app.pipeline.naver import NaverSearchClient

log = logging.getLogger(__name__)
KST = timezone(timedelta(hours=9))


@dataclass
class PipelineStats:
    collected: int = 0
    classified: int = 0
    relevant: int = 0
    issues_created: int = 0
    issues_updated: int = 0
    summarized: int = 0
    errors: list[str] = field(default_factory=list)


def _chunks(items: list, size: int):
    for i in range(0, len(items), size):
        yield items[i : i + size]


class NewsPipeline:
    def __init__(
        self,
        db: Database,
        naver: NaverSearchClient,
        llm: GeminiClient,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        batch_size: int = 25,
        max_per_run: int = 300,
        recent_hours: int = 48,
        summary_limit: int = 8,
    ):
        self._db = db
        self._naver = naver
        self._llm = llm
        self._now = now
        self._batch_size = batch_size
        self._max_per_run = max_per_run
        self._recent_hours = recent_hours
        self._summary_limit = summary_limit
        self._lock = threading.Lock()

    def run(self) -> PipelineStats | None:
        """한 번 실행한다. 이미 실행 중이면 None (스케줄러와 수동 실행이 겹치지 않게)."""
        if not self._lock.acquire(blocking=False):
            return None
        try:
            stats = PipelineStats()
            with self._db.session_factory() as session:
                stats.collected = collect_news(session, self._naver, self._now())
                relevant = self._classify(session, stats)
                changed = self._group(session, relevant, stats)
                self._summarize(session, changed, stats)
            log.info("뉴스 파이프라인 완료: %s", stats)
            return stats
        finally:
            self._lock.release()

    # ── 판별·분류 ──
    def _classify(self, session: Session, stats: PipelineStats) -> list[tuple[Article, analyzer.Classification]]:
        pending = list(session.scalars(
            select(Article).where(Article.triage == "pending").order_by(Article.published_at.desc()).limit(self._max_per_run)
        ))
        relevant = []
        for batch in _chunks(pending, self._batch_size):
            try:
                results = analyzer.classify(
                    self._llm, [analyzer.ArticleInput(a.id, a.title, a.description) for a in batch]
                )
            except LlmError as e:
                stats.errors.append(f"classify: {e}")
                continue  # 이 묶음은 pending으로 남겨 다음 실행에서 다시 판별
            for article in batch:
                result = results.get(article.id)
                if result is None:
                    continue
                stats.classified += 1
                article.triage = "relevant" if result.busan_issue else "irrelevant"
                if result.busan_issue:
                    relevant.append((article, result))
            session.commit()
        stats.relevant = len(relevant)
        return relevant

    # ── 같은 사건 묶기 + 좌표 ──
    def _group(
        self, session: Session, relevant: list[tuple[Article, analyzer.Classification]], stats: PipelineStats
    ) -> set[int]:
        if not relevant:
            return set()
        since = self._now() - timedelta(hours=self._recent_hours)
        recent = {i.id: i for i in session.scalars(
            select(Issue).where(Issue.updated_at >= since).order_by(Issue.updated_at.desc()).limit(80)
        )}
        geocoder = Geocoder(self._naver)
        changed: set[int] = set()
        created_ids: set[int] = set()

        # 오래된 기사부터 붙여야 이슈의 첫 기사·제목이 사건의 시작이 된다
        relevant.sort(key=lambda pair: pair[0].published_at)
        for batch in _chunks(relevant, 30):
            try:
                assignments = analyzer.group(
                    self._llm,
                    [analyzer.GroupInput(a.id, c.title, c.place, c.category) for a, c in batch],
                    [analyzer.GroupInput(i.id, i.title, i.place_name, i.category) for i in recent.values()],
                )
            except LlmError as e:
                stats.errors.append(f"group: {e}")
                assignments = {}  # 묶지 못하면 기사마다 따로 이슈를 만든다

            new_groups: dict[str, Issue] = {}
            for article, cls in batch:
                issue_id, group_name = assignments.get(article.id, (None, f"article-{article.id}"))
                issue = recent.get(issue_id) if issue_id else new_groups.get(group_name)
                if issue is None:
                    issue = Issue(title=cls.title or article.title[:60], category=cls.category,
                                  importance=cls.importance, place_name=cls.place, updated_at=article.published_at)
                    coords = geocoder.locate(cls.place)
                    if coords:
                        issue.lat, issue.lng = coords
                    session.add(issue)
                    session.flush()
                    new_groups[group_name] = issue
                    recent[issue.id] = issue  # 다음 묶음에서 같은 사건을 붙일 수 있게
                    created_ids.add(issue.id)
                else:
                    if issue.lat is None and cls.place:
                        coords = geocoder.locate(cls.place)
                        if coords:
                            issue.place_name = issue.place_name or cls.place
                            issue.lat, issue.lng = coords
                    if cls.importance == IMPORTANCE_HIGH:
                        issue.importance = IMPORTANCE_HIGH
                    if article.published_at > issue.updated_at:
                        issue.updated_at = article.published_at
                article.issue = issue
                changed.add(issue.id)
            session.commit()

        stats.issues_created = len(created_ids)
        stats.issues_updated = len(changed - created_ids)
        return changed

    # ── 상황 요약 (기사 2건 이상) ──
    def _summarize(self, session: Session, changed: set[int], stats: PipelineStats) -> None:
        issues = [i for i in (session.get(Issue, iid) for iid in changed) if i and len(i.articles) >= 2]
        issues.sort(key=lambda i: (i.importance != IMPORTANCE_HIGH, -len(i.articles)))
        for issue in issues[: self._summary_limit]:
            # 이번 실행에서 붙인 기사는 시간순이 아닐 수 있어 다시 정렬한다
            ordered = sorted(issue.articles, key=lambda a: a.published_at)[-10:]
            articles = [(a.published_at.astimezone(KST).strftime("%m/%d %H:%M"), a.title, a.description) for a in ordered]
            try:
                issue.status_summary = analyzer.summarize(self._llm, issue.title, articles)
                stats.summarized += 1
            except (LlmError, KeyError, TypeError) as e:
                stats.errors.append(f"summarize: {e}")
        session.commit()


class PipelineScheduler:
    """서버가 켜져 있는 동안 시작 직후와 이후 일정 간격으로 파이프라인을 돌린다."""

    def __init__(self, pipeline: NewsPipeline, interval_minutes: int):
        self._pipeline = pipeline
        self._interval = interval_minutes * 60
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, name="news-pipeline", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self._pipeline.run()
            except Exception:  # 한 번 실패해도 다음 주기에 다시 시도한다
                log.exception("뉴스 파이프라인 실행 실패")
            self._stop.wait(self._interval)
