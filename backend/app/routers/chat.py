import logging

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select

from app.chat import ChatTurn, Location, ToolBox, answer
from app.models import Issue
from app.pipeline.llm import LlmError
from app.schemas import ChatRequest, ChatResponse, IssueSummary

log = logging.getLogger(__name__)
router = APIRouter(tags=["chat"])

DEFAULT_LOCATION = Location(lat=35.1798, lng=129.075, label="부산시청 (기본 위치)")
# 모델에 보내는 이전 대화 수. 길어질수록 토큰을 많이 쓰므로 최근 몇 턴만 쓴다
HISTORY_TURNS = 6


def client_ip(request: Request) -> str:
    # 화면(Vercel)과 Render를 거쳐 오므로 X-Forwarded-For의 첫 주소가 사용자 IP다
    forwarded = request.headers.get("x-forwarded-for", "")
    return forwarded.split(",")[0].strip() or (request.client.host if request.client else "unknown")


@router.post("/chat", response_model=ChatResponse)
def chat(body: ChatRequest, request: Request) -> ChatResponse:
    """API-006 대화형 질의 (FR-006). 질문·위치·대화 내용은 저장하지 않는다 (NFR-003)."""
    state = request.app.state
    if state.chat_llm is None:
        raise HTTPException(status_code=503, detail="대화형 질의를 쓸 수 없습니다. (LLM 키 없음)")
    blocked = state.chat_limiter.check(client_ip(request))
    if blocked:
        raise HTTPException(status_code=429, detail=blocked)

    loc = body.location
    toolbox = ToolBox(
        session_factory=state.db.session_factory,
        location=Location(loc.lat, loc.lng, loc.label) if loc else DEFAULT_LOCATION,
        weather=state.weather_provider,
        air=state.air_provider,
        alerts=state.alert_provider,
        geocoder=state.chat_geocoder,
    )
    history = [ChatTurn(t.role, t.text) for t in body.history[-HISTORY_TURNS:]]
    try:
        result = answer(state.chat_llm, toolbox, body.message.strip(), history)
    except LlmError as e:
        log.warning("대화형 질의 실패: %s", str(e)[:120])
        raise HTTPException(status_code=502, detail="지금은 답변을 만들 수 없습니다. 잠시 후 다시 물어봐 주세요.")
    log.info("대화형 질의: 도구 %s", ", ".join(result.tools_used) or "없음")

    with state.db.session_factory() as session:
        found = {i.id: i for i in session.scalars(select(Issue).where(Issue.id.in_(result.issue_ids)))}
    issues = [IssueSummary.model_validate(found[i]) for i in result.issue_ids if i in found]
    return ChatResponse(answer=result.answer, issues=issues, tools_used=result.tools_used)
