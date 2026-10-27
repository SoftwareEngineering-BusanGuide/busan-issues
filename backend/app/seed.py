"""개발용 데모 데이터 넣기.

    python -m app.seed           # DB가 비어 있을 때만 넣는다
    python -m app.seed --reset   # 기존 이슈·기사를 지우고 다시 넣는다 (시각도 지금 기준으로 갱신)
"""

import argparse
from datetime import datetime, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import Database
from app.demo_data import build_demo_issues
from app.models import Article, Issue


def seed(session: Session, reset: bool = False) -> int:
    """넣은 이슈 수를 돌려준다. 이미 데이터가 있고 reset이 아니면 0."""
    if reset:
        session.execute(delete(Article))
        session.execute(delete(Issue))
    elif session.scalar(select(func.count()).select_from(Issue)):
        return 0
    issues = build_demo_issues(datetime.now(timezone.utc))
    session.add_all(issues)
    session.commit()
    return len(issues)


def main() -> None:
    parser = argparse.ArgumentParser(description="데모 이슈·기사를 DB에 넣는다")
    parser.add_argument("--reset", action="store_true", help="기존 데이터를 지우고 다시 넣기")
    args = parser.parse_args()

    db = Database(settings.database_url)
    db.create_all()
    with db.session_factory() as session:
        count = seed(session, reset=args.reset)
    print(f"데모 이슈 {count}개를 넣었습니다." if count else "이미 데이터가 있어 건너뜁니다. 다시 넣으려면 --reset")


if __name__ == "__main__":
    main()
