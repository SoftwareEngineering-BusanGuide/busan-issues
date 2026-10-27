from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.air import AirKoreaProvider
from app.alerts import DemoAlertProvider, SafetyDataAlertProvider
from app.config import Settings, settings as default_settings
from app.db import Database
from app.routers import alerts, conditions, health, issues
from app.weather import KmaWeatherProvider


def create_app(database_url: str | None = None, app_settings: Settings | None = None) -> FastAPI:
    cfg = app_settings or default_settings
    db = Database(database_url or cfg.database_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        db.create_all()
        yield
        db.engine.dispose()

    app = FastAPI(title="부산 알리미 API", version="0.1.0", lifespan=lifespan)
    app.state.db = db
    # 키가 있으면 실제 데이터, 없으면 재난문자는 데모 문자, 날씨·대기질은 제공하지 않는다 (503)
    app.state.alert_provider = (
        SafetyDataAlertProvider(cfg.safety_data_api_key) if cfg.safety_data_api_key else DemoAlertProvider()
    )
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
