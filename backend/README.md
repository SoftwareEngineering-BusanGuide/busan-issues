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

### 뉴스 수집 파이프라인 (FR-008 ~ FR-010)

`NCP_CLIENT_ID`, `NCP_CLIENT_SECRET`, `GEMINI_API_KEY`가 있으면 서버가 시작될 때 한 번, 이후 30분마다 자동으로 돕니다.

1. **수집:** NAVER API HUB 뉴스 검색으로 **최근 28일**의 부산 기사를 모읍니다. 본문은 저장하지 않고 제목·검색 요약·원문 링크만 둡니다.
   - "부산"처럼 넓은 검색어는 1,000건이 반나절도 안 돼서, 과거 기사는 사고·화재·통제·공사·단수·축제 같은 구체적인 검색어를 여러 페이지 넘겨 모읍니다.
   - 한 페이지가 모두 이미 받은 기사이거나 기간보다 오래되면 그 검색어는 멈춥니다. 그래서 처음 실행만 오래 걸리고, 이후에는 새 기사만 받습니다.
2. **판별·분류:** Gemini가 기사 25건씩 부산 생활 이슈인지 판단하고, 분류·중요도·장소·한 줄 제목을 정합니다. (AI-REQ-01, 02)
   - 한 번에 최대 300건(`PIPELINE_MAX_PER_RUN`)을 판별합니다. **날짜별로 돌아가며 고르게** 뽑아서, 첫 실행부터 4주 전체의 이슈가 조금씩 나타나고 실행할수록 촘촘해집니다.
3. **같은 사건 묶기:** 기사 묶음마다 **그 시기(앞뒤 3일)와 겹치는 이슈**와 비교해 같은 사건이면 붙이고, 아니면 새 이슈를 만듭니다. (FR-010)
4. **장소 → 좌표:** 네이버 지역 검색으로 찾고, 못 찾으면 "인근"·"도로" 같은 말을 빼고 뒤에서부터 줄여 다시 찾습니다. 그래도 없으면 구·군청 좌표를 씁니다. "부산" 전체를 뜻하는 이슈는 지도에 찍지 않습니다.
5. **상황 요약:** 기사가 2건 이상인 이슈는 기사 제목·요약만 근거로 현재 상황을 요약합니다. (AI-REQ-03)

수집 상태는 `GET /api/pipeline/status`로 확인합니다. 키가 설정됐는지(값은 보이지 않음), 지금 몇 번째 실행의 어느 단계인지, 마지막 실행 결과와 오류, DB에 쌓인 기사·이슈 수를 보여줍니다.

직접 한 번 돌리려면:

```bash
python -m app.pipeline
```

- 판별하지 못한 기사(LLM 오류·한도)는 `pending`으로 남아 다음 실행에서 다시 처리합니다.
- 스키마가 바뀌면 개발용 SQLite 파일(`backend/busan_alimi.db`)을 지우고 다시 시작하세요. (아직 마이그레이션 도구가 없습니다)

### 실시간 데이터 (API 키)

`.env`에 키가 있으면 실제 데이터를 씁니다. 키가 없어도 서버는 실행됩니다.

| 데이터 | 키 | 키가 없을 때 |
|---|---|---|
| 긴급재난문자 (재난안전데이터공유플랫폼) | `SAFETY_DATA_API_KEY` | `/api/alerts` 503 (화면에 "불러올 수 없음") |
| 날씨 (기상청 단기예보) | `DATA_GO_KR_API_KEY` | `/api/weather` 503 (화면에서 숨김) |
| 미세먼지 (에어코리아) | `DATA_GO_KR_API_KEY` | `/api/air` 503 (화면에서 숨김) |
| 뉴스 이슈 (NAVER API HUB + Gemini) | `NCP_CLIENT_ID`, `NCP_CLIENT_SECRET`, `GEMINI_API_KEY` | 수집하지 않음 (지도가 비어 있음) |

- 재난문자 키는 **등록한 IP에서만** 동작합니다. 다른 네트워크에서는 503이 나고, 화면에 "불러올 수 없음"이 표시됩니다.
- 공공데이터 API는 키를 URL에 담으므로, 요청 URL을 남기는 `httpx` 로그는 꺼 두었습니다. 로그에 키가 찍히지 않게 이 설정을 유지하세요.
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
│   ├── alerts.py      # 재난문자 (재난안전데이터공유플랫폼)
│   ├── weather.py     # 날씨 (기상청 초단기실황·예보, 격자 변환)
│   ├── air.py         # 미세먼지 (에어코리아, 가까운 측정소)
│   ├── pipeline/      # 뉴스 수집 파이프라인 (python -m app.pipeline)
│   │   ├── naver.py      # NAVER API HUB 뉴스·지역 검색
│   │   ├── llm.py        # Gemini 호출 (JSON 응답, 재시도)
│   │   ├── collector.py  # 1. 수집
│   │   ├── analyzer.py   # 2·3. 판별·분류, 같은 사건 묶기, 요약 (프롬프트)
│   │   ├── geocoder.py   # 4. 장소 → 좌표
│   │   └── runner.py     # 실행 순서, 30분 스케줄러
│   └── routers/       # API 엔드포인트 (SDD 6장)
│       ├── health.py  # API-001
│       ├── issues.py  # API-002, 003, 004
│       ├── alerts.py  # API-007
│       ├── conditions.py  # 날씨·미세먼지
│       └── pipeline.py    # 수집 상태 확인
└── tests/
```

## 구현 현황

| API ID | Endpoint | 상태 |
|---|---|---|
| API-001 | `GET /api/health` | ✅ |
| API-002 | `GET /api/issues/nearby` | ✅ (`days`: 최근 며칠, 기본 7) |
| API-003 | `GET /api/issues/top` | ✅ (`days`: 최근 며칠, 기본 7) |
| API-004 | `GET /api/issues/{id}` | ✅ (기사 시간순 포함) |
| API-005 | `GET /api/issues/{id}/timeline` | ⏳ |
| API-006 | `POST /api/chat` | ⏳ |
| API-007 | `GET /api/alerts` | ✅ 실시간 |
| (추가) | `GET /api/weather?lat&lng` | ✅ 기상청 실시간 |
| (추가) | `GET /api/air?lat&lng` | ✅ 에어코리아 실시간 |
| (추가) | `GET /api/pipeline/status` | ✅ 뉴스 수집 상태 (키 값은 내보내지 않음) |
