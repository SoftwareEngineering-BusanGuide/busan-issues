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

### 데모 데이터

뉴스 수집 파이프라인이 붙기 전까지는 데모 이슈 10개로 화면을 확인합니다. (실제 사건이 아니며, 기사 링크는 `example.com`입니다)

```bash
python -m app.seed           # DB가 비어 있을 때만 넣기
python -m app.seed --reset   # 지우고 다시 넣기 (시각을 지금 기준으로 갱신)
```

### 실시간 데이터 (API 키)

`.env`에 키가 있으면 실제 데이터를 씁니다. 키가 없어도 서버는 실행됩니다.

| 데이터 | 키 | 키가 없을 때 |
|---|---|---|
| 긴급재난문자 (재난안전데이터공유플랫폼) | `SAFETY_DATA_API_KEY` | 데모 문자 (출처에 "데모 데이터" 표시) |
| 날씨 (기상청 단기예보) | `DATA_GO_KR_API_KEY` | `/api/weather` 503 (화면에서 숨김) |
| 미세먼지 (에어코리아) | `DATA_GO_KR_API_KEY` | `/api/air` 503 (화면에서 숨김) |

- 재난문자 키는 **등록한 IP에서만** 동작합니다. 다른 네트워크에서는 503이 나고, 화면에 "불러올 수 없음"이 표시됩니다. (키가 있는데 실패하면 데모 문자로 대신하지 않습니다)
- 외부 API 응답은 서버에서 캐시합니다 (재난문자 1분, 날씨·미세먼지 10분). 새로 받다 실패하면 마지막 성공 값을 씁니다.
- 미세먼지는 기준 위치에서 가장 가까운 측정소 값입니다. 측정소 좌표는 `app/air.py`의 표(동 단위 근사값)를 씁니다.

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
│   ├── schemas.py     # API 응답 형식
│   ├── constants.py   # 이슈 분류, 중요도, 기본 반경
│   ├── geo.py         # 거리 계산
│   ├── cache.py       # 외부 API 응답 캐시 (실패 시 마지막 값)
│   ├── alerts.py      # 재난문자 (재난안전데이터공유플랫폼 / 데모)
│   ├── weather.py     # 날씨 (기상청 초단기실황·예보, 격자 변환)
│   ├── air.py         # 미세먼지 (에어코리아, 가까운 측정소)
│   ├── demo_data.py   # 데모 이슈·기사
│   ├── seed.py        # python -m app.seed
│   └── routers/       # API 엔드포인트 (SDD 6장)
│       ├── health.py  # API-001
│       ├── issues.py  # API-002, 003, 004
│       ├── alerts.py  # API-007
│       └── conditions.py  # 날씨·미세먼지
└── tests/
```

## 구현 현황

| API ID | Endpoint | 상태 |
|---|---|---|
| API-001 | `GET /api/health` | ✅ |
| API-002 | `GET /api/issues/nearby` | ✅ |
| API-003 | `GET /api/issues/top` | ✅ |
| API-004 | `GET /api/issues/{id}` | ✅ (기사 시간순 포함) |
| API-005 | `GET /api/issues/{id}/timeline` | ⏳ |
| API-006 | `POST /api/chat` | ⏳ |
| API-007 | `GET /api/alerts` | ✅ 실시간 (키 없으면 데모) |
| (추가) | `GET /api/weather?lat&lng` | ✅ 기상청 실시간 |
| (추가) | `GET /api/air?lat&lng` | ✅ 에어코리아 실시간 |
