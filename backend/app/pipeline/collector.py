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

PAGE_SIZE = 100
MAX_START = 1000  # 네이버 검색은 한 검색어당 최대 1,000번째 결과까지 준다

# (검색어, 최대 페이지 수).
# "부산"은 기사가 너무 많아 1,000건이 반나절도 안 되므로 최신 기사용으로만 쓴다.
# 과거(몇 주 전) 기사는 결과가 적은 구체적인 검색어를 여러 페이지 넘겨 가며 모은다.
NEWS_QUERIES: tuple[tuple[str, int], ...] = (
    ("부산", 3),
    ("부산 사고", 10), ("부산 교통사고", 10), ("부산 화재", 10), ("부산 싱크홀", 3), ("부산 땅꺼짐", 3),
    ("부산 붕괴", 5), ("부산 침수", 5), ("부산 호우", 5), ("부산 태풍", 5), ("부산 강풍", 5),
    ("부산 교통 통제", 10), ("부산 도로 통제", 10), ("부산 공사", 10), ("부산 단수", 5), ("부산 정전", 5),
    ("부산 축제", 10), ("부산 행사 개최", 10), ("부산 구청", 10),
)


def _parse(item: dict) -> tuple[str, datetime] | None:
    url = item.get("originallink") or item.get("link")
    try:
        return (url, parsedate_to_datetime(item["pubDate"])) if url else None
    except (KeyError, TypeError, ValueError):
        return None


def collect_news(session: Session, naver: NaverSearchClient, now: datetime, max_age_days: int = 28) -> int:
    """최근 max_age_days일 안의 새 기사를 'pending' 상태로 저장하고, 저장한 수를 돌려준다.

    검색 결과는 최신순이라, 한 페이지가 모두 이미 아는 기사이거나 기간보다 오래되면 그 검색어는 그만 넘긴다.
    그래서 처음 실행할 때만 여러 페이지를 받고, 이후 실행은 대부분 첫 페이지에서 끝난다.
    """
    since = now - timedelta(days=max_age_days)
    known = set(session.scalars(select(Article.url).where(Article.published_at >= since)))
    found: dict[str, Article] = {}

    for query, max_pages in NEWS_QUERIES:
        for page in range(max_pages):
            start = page * PAGE_SIZE + 1
            if start > MAX_START:
                break
            try:
                items = naver.search_news(query, display=PAGE_SIZE, start=start)
            except httpx.HTTPError as e:
                log.warning("뉴스 검색 실패 (%s, %d쪽): %s", query, page + 1, e)
                break
            page_has_new = False
            reached_old = False
            for item in items:
                parsed = _parse(item)
                if not parsed:
                    continue
                url, published = parsed
                if published < since:
                    reached_old = True
                    continue
                if url in known or url in found:
                    continue
                page_has_new = True
                found[url] = Article(
                    title=clean_text(item.get("title", "")),
                    description=clean_text(item.get("description", "")),
                    url=url,
                    published_at=published,
                    triage="pending",
                )
            if len(items) < PAGE_SIZE or reached_old or not page_has_new:
                break

    if not found:
        return 0
    # 기간 밖이라 known에 없던 오래된 기사와 겹칠 수 있어 한 번 더 확인한다 (DB 변수 개수 제한 때문에 나눠서)
    urls = list(found)
    existing: set[str] = set()
    for i in range(0, len(urls), 500):
        existing.update(session.scalars(select(Article.url).where(Article.url.in_(urls[i : i + 500]))))
    new = [a for url, a in found.items() if url not in existing]
    session.add_all(new)
    session.commit()
    return len(new)
