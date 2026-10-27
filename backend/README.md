# Backend (FastAPI)

부산 알리미 API 서버입니다. 설계는 SDD 2장(아키텍처), 5장(DB), 6장(API)을 따릅니다.

## 준비

Python **3.11 이상**이 필요합니다.

```bash
cd backend
python3 -m venv .venv            # 또는: uv venv --python 3.12 .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

환경변수는 저장소 루트의 `.env`에서 읽습니다. (`cp .env.example .env`)

| 변수 | 기본값 | 설명 |
|---|---|---|
| `DATABASE_URL` | `backend/busan_alimi.db` (SQLite) | PostgreSQL 전환 시 `postgresql+psycopg://...` 형식으로 지정 |
| `CORS_ORIGINS` | `http://localhost:5173` | 프론트엔드 개발 서버 주소 (쉼표로 여러 개) |

## 실행

```bash
uvicorn app.main:app --reload
```

- 상태 확인: http://localhost:8000/api/health → `{"status": "ok", "database": "ok"}`
- API 문서 (자동 생성): http://localhost:8000/docs

서버를 처음 시작하면 `issues`, `articles` 테이블이 자동으로 만들어집니다.

## 테스트

```bash
pytest
```

## 구조

```
backend/
├── app/
│   ├── main.py        # 앱 생성, 라우터·CORS 등록
│   ├── config.py      # 환경변수 설정
│   ├── db.py          # DB 연결, 세션
│   ├── models.py      # issues, articles 테이블 (SDD 5.2)
│   └── routers/       # API 엔드포인트 (SDD 6장)
│       └── health.py  # API-001 GET /api/health
└── tests/
```

## 구현 현황

| API ID | Endpoint | 상태 |
|---|---|---|
| API-001 | `GET /api/health` | ✅ |
| API-002 | `GET /api/issues/nearby` | ⏳ |
| API-003 | `GET /api/issues/top` | ⏳ |
| API-004 | `GET /api/issues/{id}` | ⏳ |
| API-005 | `GET /api/issues/{id}/timeline` | ⏳ |
| API-006 | `POST /api/chat` | ⏳ |
| API-007 | `GET /api/alerts` | ⏳ |
