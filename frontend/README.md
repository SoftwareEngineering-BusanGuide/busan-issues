# Frontend (React + Vite)

부산 알리미 웹 화면입니다. SRS 6.1 화면 목록 중 v0.1에서 아래를 구현했습니다.

| 화면 | 내용 | 요구사항 |
|---|---|---|
| UI-01 메인 지도 | 내 주변 이슈 마커·반경, 상단 부산 주요 이슈와 기준 위치의 날씨·미세먼지, 하단 실시간 재난문자 띠 | FR-002, FR-003, FR-007 |
| UI-02 이슈 상세 | 상황 요약, 관련 기사 시간순 목록, 원문 링크 | FR-004, FR-005 |
| 지도 레이어 | 오른쪽 위 🗂️ 레이어 패널에서 뉴스 이슈·위성사진·기온·바람·미세먼지를 켜고 끔 (선택은 브라우저에 기억). 기온은 지도 전체에 색으로 깔리고, 바람은 흐르는 입자 애니메이션 | FR-002, FR-007 |
| UI-05 위치·필터 | 내 위치(브라우저 권한) 또는 구·군·**부산 전체** 선택, 반경(기본 10km), 기간(24시간·7일·30일), 카테고리 필터 | FR-001, FR-011 |

### 모바일 (화면 너비 768px 미만)

- 오른쪽 패널 대신 **바텀시트**: 살짝(제목 줄만) → 절반 → 전체 세 단계. 제목 줄을 끌거나 눌러서 바꿉니다.
- 위치·반경·기간은 지도 위 **요약 칩**(`📍 부산시청 · 10km · 7일`)을 눌러 바꿉니다.
- 재난문자 띠는 화면 위쪽에 둡니다.
- 마커나 주요 이슈를 누르면 시트가 절반으로 올라와 상세를 보여 주고, 지도는 그 마커를 위쪽 절반 가운데로 옮깁니다. 목록으로 돌아가면 시트가 원래 높이로 돌아갑니다.
- 바람 입자 수를 줄여 휴대폰 배터리·발열을 줄였습니다.

### 홈 화면 앱 (iPhone)

Safari 공유 → **홈 화면에 추가**하면 주소창 없는 전체 화면 앱으로 열립니다. (`public/manifest.webmanifest`, `public/icons/`, `index.html`의 apple 메타 태그) 오프라인 캐시(서비스 워커)는 없습니다.

- 홈 화면 앱은 처음 열릴 때 화면 높이를 실제보다 작게 알려 줘서 지도 아래쪽이 검게 남는 문제가 있었습니다. `src/lib/viewport.ts`가 실행 직후 여러 번, 그리고 화면이 바뀔 때마다 높이를 다시 재서 `--app-height`로 쓰고 지도 크기를 다시 맞춥니다.
- 다른 앱에 다녀오는 동안 iOS가 지도 그래픽(WebGL)을 회수하면, 돌아왔을 때 페이지를 새로 불러옵니다.
- 노치·홈바 영역(safe area)만큼 상단 바와 시트에 여백을 둡니다.
- 아이콘을 바꾼 뒤에는 홈 화면의 기존 아이콘을 지우고 다시 추가해야 반영됩니다.

지도의 이슈는 백엔드 뉴스 수집 파이프라인이 실제 기사로 만든 데이터입니다. 이슈 상세에는 기사별 언론사 주소와 "AI가 정리했다"는 안내를 표시합니다.

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
│   ├── map/IssueMap.tsx    # 지도, 마커, 기준 위치·반경, 위성사진·날씨·바람·미세먼지 레이어
│   ├── map/LayerControl.tsx  # 레이어 패널과 범례
│   ├── map/windParticles.ts  # 바람 입자 애니메이션
│   ├── panel/              # LocationControl, IssueList, IssueDetailView, 모바일 BottomSheet·LocationChip
│   └── ticker/             # AlertTicker (재난문자·특보)
├── hooks/useMediaQuery.ts  # 데스크톱/모바일 화면 구분
├── lib/                    # 상수(구·군 좌표, 카테고리), 날짜·거리 형식, 좌표 계산, 기온·바람 격자 보간(weatherField.ts), 화면 높이 측정(viewport.ts)
└── types.ts                # 백엔드 응답 타입
```
