from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.alerts import DemoAlertProvider
from app.config import settings
from app.db import Database
from app.routers import alerts, health, issues


def create_app(database_url: str | None = None) -> FastAPI:
    db = Database(database_url or settings.database_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        db.create_all()
        yield
        db.engine.dispose()

    app = FastAPI(title="부산 알리미 API", version="0.1.0", lifespan=lifespan)
    app.state.db = db
    # 공공데이터 API 키를 받으면 실제 재난문자 제공자로 교체한다
    app.state.alert_provider = DemoAlertProvider()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    for router in (health.router, issues.router, alerts.router):
        app.include_router(router, prefix="/api")
    return app


app = create_app()
