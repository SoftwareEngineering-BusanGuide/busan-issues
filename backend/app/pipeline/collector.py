"""1단계: 뉴스 수집 (FR-008). 본문은 저장하지 않고 제목·검색 요약·원문 링크만 둔다 (SRS 2.4)."""

import logging
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Article
from app.pipeline.naver import NaverSearchClient, clean_text

log = logging.getLogger(__name__)

# 생활 이슈를 넓게 잡기 위한 검색어. 결과에 부산과 무관한 기사가 섞여도 다음 단계(판별)에서 걸러낸다.
NEWS_QUERIES = ("부산", "부산 사고", "부산 화재", "부산 교통 통제", "부산 공사", "부산 축제")


def collect_news(session: Session, naver: NaverSearchClient, now: datetime, max_age_hours: int = 24) -> int:
    """새 기사를 'pending' 상태로 저장하고, 저장한 수를 돌려준다."""
    since = now - timedelta(hours=max_age_hours)
    found: dict[str, Article] = {}
    for query in NEWS_QUERIES:
        try:
            items = naver.search_news(query)
        except httpx.HTTPError as e:
            log.warning("뉴스 검색 실패 (%s): %s", query, e)
            continue
        for item in items:
            url = item.get("originallink") or item.get("link")
            try:
                published = parsedate_to_datetime(item["pubDate"])
            except (KeyError, TypeError, ValueError):
                continue
            if not url or published < since or url in found:
                continue
            found[url] = Article(
                title=clean_text(item.get("title", "")),
                description=clean_text(item.get("description", "")),
                url=url,
                published_at=published,
                triage="pending",
            )

    if not found:
        return 0
    existing = set(session.scalars(select(Article.url).where(Article.url.in_(found))))
    new = [a for url, a in found.items() if url not in existing]
    session.add_all(new)
    session.commit()
    return len(new)
