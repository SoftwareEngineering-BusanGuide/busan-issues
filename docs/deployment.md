# 배포 가이드

부산 알리미는 무료 플랜 두 곳에 나눠 배포합니다.

| 구성 | 서비스 | 설정 파일 | 주소 (예) |
|---|---|---|---|
| 화면 (React) | **Vercel** Hobby (무료) | `frontend/vercel.json` | `https://<프로젝트>.vercel.app` |
| 서버 (FastAPI) | **Render** Free | `render.yaml` | `https://busan-alimi-api.onrender.com` |

화면에서 `/api/...`로 보낸 요청은 Vercel이 Render 서버로 넘깁니다 (`vercel.json`의 rewrites). 그래서 브라우저 입장에서는 같은 주소라 CORS 설정이 필요 없습니다.

> 두 서비스 모두 **`main` 브랜치**를 배포합니다. `main`에 병합되면 자동으로 다시 배포됩니다.

## 1. Render (서버)

1. [render.com](https://render.com)에 **GitHub 계정으로 가입**합니다. (카드 불필요)
2. GitHub 연결 화면에서 **SoftwareEngineering-BusanGuide 조직의 `busan-issues` 저장소 접근을 허용**합니다.
   - 조직 저장소라 **조직 관리자(Owner)의 승인**이 필요할 수 있습니다. 승인 요청이 뜨면 관리자에게 부탁하세요.
3. Render 대시보드에서 **New → Blueprint**를 누르고 `busan-issues` 저장소를 고릅니다.
4. `render.yaml`을 읽어 `busan-alimi-api` 서비스가 표시됩니다. API 키 입력 칸에 팀 채널로 공유받은 값을 넣습니다.
   - `DATA_GO_KR_API_KEY`, `SAFETY_DATA_API_KEY`, `NCP_CLIENT_ID`, `NCP_CLIENT_SECRET`, `GEMINI_API_KEY`
5. **Apply**를 누르고 배포가 끝날 때까지 기다립니다. (처음에는 몇 분 걸립니다)
6. 브라우저에서 `https://<서비스 주소>/api/health`를 열어 `{"status":"ok","database":"ok"}`가 나오는지 확인합니다.
7. 서비스 주소가 `busan-alimi-api.onrender.com`과 다르면 (이름이 이미 쓰이는 경우 뒤에 글자가 붙음), `frontend/vercel.json`의 `destination` 주소를 바꿔 PR로 올립니다.

## 2. Vercel (화면)

1. [vercel.com](https://vercel.com)에 **GitHub 계정으로 가입**합니다. (Hobby 플랜, 무료)
2. **Add New → Project**에서 `busan-issues` 저장소를 **Import**합니다. (조직 저장소 접근 허용이 필요할 수 있습니다)
3. 설정 화면에서 **Root Directory를 `frontend`**로 바꿉니다. Framework Preset은 Vite로 자동 인식됩니다.
   - Build Command: `npm run build` / Output Directory: `dist` (기본값 그대로)
4. **Deploy**를 누릅니다. 끝나면 `https://<프로젝트>.vercel.app` 주소가 생깁니다.
5. 주소를 열어 지도, 상단 날씨·미세먼지, 재난문자 띠가 나오는지 확인합니다.

API 키는 Vercel에는 넣지 않습니다. 화면은 키 없이 서버만 호출합니다.

## 무료 플랜에서 알아둘 점

- **서버가 잠듭니다:** Render 무료 서버는 15분 동안 요청이 없으면 잠들고, 다시 깨어나는 데 1분 정도 걸립니다. 그동안 화면에 "서버에 연결할 수 없습니다"가 잠깐 보일 수 있고, 1분마다 다시 불러오므로 서버가 깨면 자동으로 채워집니다. 발표나 시연 직전에는 `/api/health`를 한 번 열어 미리 깨워 두세요.
- **데이터가 초기화됩니다:** 무료 플랜은 디스크가 유지되지 않아, 재시작·재배포마다 SQLite DB가 비고 시작 명령이 데모 이슈를 다시 넣습니다. 뉴스 수집 데이터를 유지하려면 나중에 무료 PostgreSQL(Neon, Supabase 등)을 붙이고 `DATABASE_URL`을 설정해야 합니다.
- **재난문자는 실패할 수 있습니다:** 재난문자 API는 등록한 IP에서만 동작하는데, Render 서버의 IP는 등록돼 있지 않습니다. 이때 화면 하단에 "실시간 재난문자를 일시적으로 불러올 수 없습니다"가 표시되며, 정상 동작입니다. 재난문자까지 상시로 보여주려면 고정 IP가 있는 서버(예: 오라클 클라우드 무료 VM)로 옮기고 그 IP를 추가로 등록해야 합니다.
- **API 키 공개 주의:** 키는 Render 환경변수에만 넣고 저장소에는 절대 커밋하지 않습니다. 대화형 질의(Gemini)를 붙이기 전에 요청 횟수 제한을 먼저 넣어야 합니다.
