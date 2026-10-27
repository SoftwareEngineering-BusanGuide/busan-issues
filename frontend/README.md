# Frontend (React + Vite)

부산 알리미 웹 화면입니다. SRS 6.1 화면 목록 중 v0.1에서 아래를 구현했습니다.

| 화면 | 내용 | 요구사항 |
|---|---|---|
| UI-01 메인 지도 | 내 주변 이슈 마커·반경, 상단 부산 주요 이슈와 기준 위치의 날씨·미세먼지, 하단 실시간 재난문자 띠 | FR-002, FR-003, FR-007 |
| UI-02 이슈 상세 | 상황 요약, 관련 기사 시간순 목록, 원문 링크 | FR-004, FR-005 |
| UI-05 위치·필터 | 내 위치(브라우저 권한) 또는 구·군 선택, 반경, 카테고리 필터 | FR-001, FR-011 |

지도는 아직 Kakao Maps 대신 키 없이 쓸 수 있는 **MapLibre + CARTO 베이스맵**을 씁니다. Kakao JavaScript 키를 받으면 `src/components/map/IssueMap.tsx`만 교체합니다.

## 실행

백엔드가 먼저 떠 있어야 합니다. ([`backend/README.md`](../backend/README.md))

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173
```

개발 서버는 `/api` 요청을 `http://localhost:8000`(FastAPI)으로 넘깁니다. (`vite.config.ts`)

## 검사·빌드

```bash
npm run lint       # oxlint
npm run build      # 타입 검사 + 빌드
```

## 구조

```
src/
├── App.tsx                 # 화면 배치, 위치·선택 상태, API 호출
├── api/client.ts           # 백엔드 API (API-002, 003, 004, 007, 날씨, 미세먼지)
├── components/
│   ├── header/             # TopBar, TopIssues (부산 주요 이슈)
│   ├── map/IssueMap.tsx    # 지도, 마커, 기준 위치·반경
│   ├── panel/              # LocationControl, IssueList, IssueDetailView
│   └── ticker/             # AlertTicker (재난문자·특보)
├── lib/                    # 상수(구·군 좌표, 카테고리), 날짜·거리 형식, 좌표 계산
└── types.ts                # 백엔드 응답 타입
```
