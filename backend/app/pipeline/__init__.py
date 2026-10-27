from app.config import Settings
from app.db import Database
from app.pipeline.llm import GeminiClient
from app.pipeline.naver import NaverSearchClient
from app.pipeline.runner import NewsPipeline, PipelineScheduler, PipelineStats


def build_pipeline(db: Database, settings: Settings) -> NewsPipeline:
    return NewsPipeline(
        db,
        NaverSearchClient(settings.ncp_client_id, settings.ncp_client_secret),
        GeminiClient(settings.gemini_api_key, settings.gemini_model),
        max_age_days=settings.news_max_age_days,
        max_per_run=settings.pipeline_max_per_run,
    )


__all__ = ["NewsPipeline", "PipelineScheduler", "PipelineStats", "build_pipeline"]
