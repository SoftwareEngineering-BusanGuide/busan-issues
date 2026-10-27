"""수동 실행: python -m app.pipeline"""

import logging

from app.config import settings
from app.db import Database
from app.pipeline import build_pipeline


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)  # 요청 URL에 담긴 API 키가 로그에 찍히지 않게
    if not (settings.ncp_client_id and settings.ncp_client_secret and settings.gemini_api_key):
        raise SystemExit(".env에 NCP_CLIENT_ID, NCP_CLIENT_SECRET, GEMINI_API_KEY가 필요합니다.")
    db = Database(settings.database_url)
    db.create_all()
    stats = build_pipeline(db, settings).run()
    print(stats)


if __name__ == "__main__":
    main()
