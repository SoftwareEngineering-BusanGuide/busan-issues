import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.air import AirKoreaProvider
from app.alerts import SafetyDataAlertProvider
from app.config import Settings, settings as default_settings
from app.db import Database
from app.pipeline import PipelineScheduler, build_pipeline
from app.routers import alerts, conditions, health, issues
from app.weather import KmaWeatherProvider

# 뉴스 파이프라인 진행 로그를 서버 로그에서 볼 수 있게 한다
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
# httpx는 요청 URL 전체를 INFO로 남기는데, 공공데이터 API는 키를 URL(serviceKey)에 담으므로 로그에 키가 찍히지 않게 끈다
logging.getLogger("httpx").setLevel(logging.WARNING)


def create_app(database_url: str | None = None, app_settings: Settings | None = None) -> FastAPI:
    cfg = app_settings or default_settings
    db = Database(database_url or cfg.database_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        db.create_all()
        scheduler = None
        if cfg.pipeline_ready:
            # 시작하자마자 한 번, 이후 일정 간격으로 뉴스를 모아 이슈를 만든다 (FR-008 ~ FR-010)
            scheduler = PipelineScheduler(build_pipeline(db, cfg), cfg.pipeline_interval_minutes)
            scheduler.start()
        yield
        if scheduler:
            scheduler.stop()
        db.engine.dispose()

    app = FastAPI(title="부산 알리미 API", version="0.2.0", lifespan=lifespan)
    app.state.db = db
    # 키가 없으면 해당 기능은 None → 503 (화면에서 숨김)
    app.state.alert_provider = SafetyDataAlertProvider(cfg.safety_data_api_key) if cfg.safety_data_api_key else None
    app.state.weather_provider = KmaWeatherProvider(cfg.data_go_kr_api_key) if cfg.data_go_kr_api_key else None
    app.state.air_provider = AirKoreaProvider(cfg.data_go_kr_api_key) if cfg.data_go_kr_api_key else None

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.cors_origin_list,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    for router in (health.router, issues.router, alerts.router, conditions.router):
        app.include_router(router, prefix="/api")
    return app


app = create_app()
