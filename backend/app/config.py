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

    # 외부 데이터 API 키. 비어 있으면 재난문자는 데모 문자를 쓰고, 날씨·대기질은 제공하지 않는다.
    data_go_kr_api_key: str = ""  # 기상청 단기예보, 에어코리아 (공공데이터포털)
    safety_data_api_key: str = ""  # 긴급재난문자 (재난안전데이터공유플랫폼, 등록한 IP에서만 호출 가능)

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
