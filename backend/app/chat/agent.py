"""대화형 질의 (FR-006): LLM이 도구로 이슈·날씨·재난문자를 찾아보고, 그 결과로만 답한다 (AI-REQ, NFR-005)."""

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol

from app.chat.tools import DECLARATIONS, ToolBox

KST = timezone(timedelta(hours=9))
MAX_TOOL_ROUNDS = 5
ISSUE_REF = re.compile(r"\[#(\d+)\]")
WEEKDAYS = "월화수목금토일"

SYSTEM_PROMPT = """너는 '부산 알리미'의 안내원이다. 부산 사용자가 동네 소식, 사고·공사·교통 통제·행사, 날씨, 미세먼지, 재난문자를 물으면 도구로 찾아보고 답한다.

지금: {now}
사용자의 기준 위치: {label} (위도 {lat:.4f}, 경도 {lng:.4f}). 장소를 말하지 않으면 이 위치를 기준으로 한다.

규칙:
1. 사실은 반드시 도구 결과에서만 가져온다. 도구 결과에 없는 사건·수치·날짜를 지어내지 않는다. 찾지 못했으면 '확인된 소식이 없다'고 말한다.
2. 다른 장소를 물으면 find_place로 좌표를 얻은 뒤 다른 도구에 그 좌표를 넘긴다.
3. '가도 괜찮을까', '나가도 될까' 같은 질문은 그 장소·날짜의 이슈, 날씨 예보, 미세먼지를 함께 보고 종합한다. 위험하다고 단정하거나 안전을 보장하지 말고, 확인한 사실과 참고할 점을 말한다.
4. 이슈를 말할 때는 제목 뒤에 [#이슈id]를 붙인다. 예: 해운대 해변로 공사 [#12]. 도구 결과에 있는 id만 쓴다.
5. 답 끝에 출처를 한 줄로 적는다. 예: 출처: 뉴스 이슈 2건, 기상청 단기예보
6. 한국어 존댓말(~요)로, 짧게(5문장 안팎) 답한다. 목록이 필요하면 '- '로 시작하는 줄을 쓴다. 표·제목(#)·굵은 글씨는 쓰지 않는다.
7. 부산 지역 소식·날씨·안전과 관계없는 질문(일반 상식, 코딩, 잡담 등)에는 이 서비스가 답할 수 있는 범위를 짧게 안내한다.
8. 긴급 상황이면 119·112에 신고하라고 먼저 말한다."""


class ToolLlm(Protocol):
    def generate_with_tools(self, system: str, contents: list[dict], tools: list[dict], allow_tools: bool = True) -> dict: ...


@dataclass
class ChatTurn:
    role: str  # user / assistant
    text: str


@dataclass
class ChatResult:
    answer: str
    issue_ids: list[int]
    tools_used: list[str]


def build_system_prompt(toolbox: ToolBox, now: datetime) -> str:
    local = now.astimezone(KST)
    loc = toolbox.location
    stamp = f"{local:%Y-%m-%d} ({WEEKDAYS[local.weekday()]}) {local:%H:%M} (한국 시간)"
    return SYSTEM_PROMPT.format(now=stamp, label=loc.label, lat=loc.lat, lng=loc.lng)


def answer(llm: ToolLlm, toolbox: ToolBox, message: str, history: list[ChatTurn]) -> ChatResult:
    contents = [{"role": "model" if t.role == "assistant" else "user", "parts": [{"text": t.text}]} for t in history]
    contents.append({"role": "user", "parts": [{"text": message}]})
    system = build_system_prompt(toolbox, toolbox.now())
    tools_used: list[str] = []

    for round_ in range(MAX_TOOL_ROUNDS + 1):
        # 마지막 차례에는 도구를 막아 반드시 글로 답하게 한다
        content = llm.generate_with_tools(system, contents, DECLARATIONS, allow_tools=round_ < MAX_TOOL_ROUNDS)
        calls = [p["functionCall"] for p in content.get("parts", []) if "functionCall" in p]
        if not calls:
            text = "".join(p.get("text", "") for p in content.get("parts", []) if not p.get("thought")).strip()
            return _finish(text, toolbox, tools_used)

        # 모델 응답(서명 포함)을 그대로 기록에 붙이고, 도구 결과를 한 번에 돌려준다
        contents.append({"role": "model", "parts": content["parts"]})
        responses = []
        for call in calls:
            name = call.get("name", "")
            tools_used.append(name)
            response = {"name": name, "response": toolbox.call(name, call.get("args") or {})}
            if "id" in call:
                response["id"] = call["id"]
            responses.append({"functionResponse": response})
        contents.append({"role": "user", "parts": responses})

    return _finish("", toolbox, tools_used)


def _finish(text: str, toolbox: ToolBox, tools_used: list[str]) -> ChatResult:
    if not text:
        text = "답변을 만들지 못했습니다. 질문을 조금 바꿔 다시 물어봐 주세요."
    issue_ids: list[int] = []

    def keep_known(match: re.Match) -> str:
        # 도구 결과에 없던 id는 지어낸 것이므로 지운다
        issue_id = int(match.group(1))
        if issue_id not in toolbox.seen_issue_ids:
            return ""
        if issue_id not in issue_ids:
            issue_ids.append(issue_id)
        return match.group(0)

    text = ISSUE_REF.sub(keep_known, text)
    issue_ids += [i for i in toolbox.focused_issue_ids if i not in issue_ids]
    return ChatResult(answer=text, issue_ids=issue_ids, tools_used=tools_used)
