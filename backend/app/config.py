from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# 저장소 루트의 .env를 읽는다 (backend/app/config.py 기준 두 단계 위)
REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    # .env.example을 그대로 복사해 값이 비어 있어도 기본값을 쓰도록 빈 값은 무시한다
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore", env_ignore_empty=True)

    # 개발은 SQLite로 시작하고, 배포 시 PostgreSQL URL로 바꾼다 (SDD ADR-004)
    database_url: str = f"sqlite:///{REPO_ROOT / 'backend' / 'busan_alimi.db'}"
    # 프론트엔드 개발 서버 주소 (쉼표로 여러 개)
    cors_origins: str = "http://localhost:5173"

    # 외부 데이터 API 키. 비어 있으면 해당 기능은 503을 돌려주고 화면에서 숨긴다.
    data_go_kr_api_key: str = ""  # 기상청 단기예보, 에어코리아 (공공데이터포털)
    safety_data_api_key: str = ""  # 긴급재난문자 (재난안전데이터공유플랫폼, 등록한 IP에서만 호출 가능)
    ncp_client_id: str = ""  # NAVER API HUB: 뉴스 검색, 지역 검색
    ncp_client_secret: str = ""
    gemini_api_key: str = ""  # 기사 판별·분류·장소 추출·묶기·요약

    # 뉴스 수집 파이프라인 (FR-008 ~ FR-010). 네이버·Gemini 키가 모두 있을 때만 동작한다.
    pipeline_enabled: bool = True
    pipeline_interval_minutes: int = 30  # NFR-002: 게시 후 30분 안에 반영
    news_max_age_days: int = 28  # 이 기간 안의 기사까지 모은다 (과거 이슈 포함)
    pipeline_max_per_run: int = 300  # 한 번에 판별할 최대 기사 수 (Gemini 한도 보호). 나머지는 다음 실행에서
    gemini_model: str = "gemini-3.5-flash-lite"

    @property
    def pipeline_ready(self) -> bool:
        return self.pipeline_enabled and bool(self.ncp_client_id and self.ncp_client_secret and self.gemini_api_key)

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
