from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError

from app.models import Article, Issue


def test_tables_created_on_startup(client: TestClient):
    tables = inspect(client.app.state.db.engine).get_table_names()
    assert {"issues", "articles"} <= set(tables)


def test_issue_groups_articles_in_time_order(client: TestClient):
    with client.app.state.db.session_factory() as session:
        issue = Issue(
            title="하단동 도로 싱크홀",
            category="사고",
            importance="high",
            place_name="사하구 하단동",
            lat=35.1066,
            lng=128.9668,
            updated_at=datetime(2026, 9, 30, 12, tzinfo=timezone.utc),
        )
        issue.articles = [
            Article(title="후속 보도", description="복구 진행", url="https://news.example/2",
                    published_at=datetime(2026, 9, 30, 12, tzinfo=timezone.utc)),
            Article(title="첫 보도", description="싱크홀 발생", url="https://news.example/1",
                    published_at=datetime(2026, 9, 30, 9, tzinfo=timezone.utc)),
        ]
        session.add(issue)
        session.commit()
        issue_id = issue.id

    with client.app.state.db.session_factory() as session:
        saved = session.get(Issue, issue_id)
        assert [a.title for a in saved.articles] == ["첫 보도", "후속 보도"]
        assert saved.lat == pytest.approx(35.1066)


def test_article_url_is_unique(client: TestClient):
    published = datetime(2026, 9, 30, tzinfo=timezone.utc)
    with client.app.state.db.session_factory() as session:
        session.add(Article(title="a", description="a", url="https://news.example/dup", published_at=published))
        session.commit()
        session.add(Article(title="b", description="b", url="https://news.example/dup", published_at=published))
        with pytest.raises(IntegrityError):
            session.commit()


def test_article_can_exist_without_issue(client: TestClient):
    with client.app.state.db.session_factory() as session:
        session.add(Article(title="미분류", description="", url="https://news.example/3",
                            published_at=datetime(2026, 9, 30, tzinfo=timezone.utc)))
        session.commit()
        assert session.scalars(select(Article).where(Article.issue_id.is_(None))).one().title == "미분류"
