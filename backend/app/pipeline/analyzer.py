"""2~3단계와 요약: Gemini로 기사 판별·분류·장소 추출(AI-REQ-01, 02), 같은 사건 묶기(FR-010), 상황 요약(AI-REQ-03).

LLM에는 기사 제목·검색 요약만 주고, 그 안에 없는 내용을 만들지 않도록 지시한다.
"""

import json
from dataclasses import dataclass

from app.constants import CATEGORIES, IMPORTANCE_HIGH, IMPORTANCE_NORMAL
from app.pipeline.llm import GeminiClient


@dataclass
class Classification:
    busan_issue: bool
    category: str
    importance: str
    place: str | None
    title: str


@dataclass
class ArticleInput:
    id: int
    title: str
    description: str


CLASSIFY_PROMPT = """너는 부산 지역 소식 지도 서비스의 편집자다. 아래 뉴스 기사(제목·요약)를 하나씩 판단해 JSON 배열로 답해라.

[busan_issue]
- true: 부산광역시 안에서 일어났거나 부산 시민의 생활에 직접 영향을 주는 구체적인 사건·소식
  (사건·사고, 화재, 재난·기상 피해, 교통 통제·혼잡, 공사·단수·정전, 시·구청의 생활 행정 소식, 지역 축제·행사)
- false: 기고·사설·칼럼·인터뷰·좌담·화보, 기업·금융·증권·부동산 시세, 기업 홍보(매장 입점·신상품·이벤트·채용),
  정치 일반, 재판 결과만 다룬 기사, 스포츠 경기, 연예, 항공 노선 취항,
  부산이 아닌 지역(경남·울산·서울 등)의 소식이나 다른 지역 기관의 방문·교류, 부산이 이름만 언급된 기사
[category] {categories} 중 하나 (busan_issue가 false여도 가장 가까운 값)
[importance] high: 부산 전역에 영향을 주거나 인명 피해·대형 사고·재난·대규모 교통 통제·기상특보. 그 외 normal
[place] 기사에 적힌 부산 안의 가장 구체적인 장소 (예: "사하구 하단동 낙동대로", "해운대해수욕장").
  "부산", "부산시"처럼 부산 전체를 뜻하거나 기사에 장소가 없으면 null. 추측하지 마라
[title] 사건을 25자 이내로 요약한 제목. 기사에 없는 내용을 넣지 마라

기사:
{articles}"""

CLASSIFY_SCHEMA = {
    "type": "ARRAY",
    "items": {
        "type": "OBJECT",
        "properties": {
            "id": {"type": "INTEGER"},
            "busan_issue": {"type": "BOOLEAN"},
            "category": {"type": "STRING", "enum": list(CATEGORIES)},
            "importance": {"type": "STRING", "enum": [IMPORTANCE_HIGH, IMPORTANCE_NORMAL]},
            "place": {"type": "STRING", "nullable": True},
            "title": {"type": "STRING"},
        },
        "required": ["id", "busan_issue", "category", "importance", "place", "title"],
    },
}


def classify(llm: GeminiClient, articles: list[ArticleInput]) -> dict[int, Classification]:
    """기사 id → 판별 결과. LLM이 빠뜨린 기사는 결과에 없다 (다음 실행에서 다시 판별)."""
    payload = [{"id": a.id, "title": a.title, "description": a.description[:300]} for a in articles]
    prompt = CLASSIFY_PROMPT.format(categories=", ".join(CATEGORIES), articles=json.dumps(payload, ensure_ascii=False))
    valid_ids = {a.id for a in articles}
    result = {}
    for row in llm.generate_json(prompt, CLASSIFY_SCHEMA):
        if row.get("id") not in valid_ids or row.get("category") not in CATEGORIES:
            continue
        result[row["id"]] = Classification(
            busan_issue=bool(row.get("busan_issue")),
            category=row["category"],
            importance=IMPORTANCE_HIGH if row.get("importance") == IMPORTANCE_HIGH else IMPORTANCE_NORMAL,
            place=(row.get("place") or "").strip() or None,
            title=(row.get("title") or "").strip()[:60],
        )
    return result


GROUP_PROMPT = """부산 지역 이슈 목록과 새 기사 목록이 있다. 새 기사가 기존 이슈와 '같은 사건'이면 그 issue_id를,
아니면 null을 넣어라. 같은 사건이란 같은 장소·같은 시기의 하나의 사고·통제·행사 등을 말한다 (분류만 같은 것은 다른 사건).
기존 이슈에 없는 새 사건끼리 같은 사건이면 group에 같은 짧은 이름을 넣어라. 서로 다른 사건이면 group을 다르게 해라.

기존 이슈:
{issues}

새 기사:
{articles}"""

GROUP_SCHEMA = {
    "type": "ARRAY",
    "items": {
        "type": "OBJECT",
        "properties": {
            "id": {"type": "INTEGER"},
            "issue_id": {"type": "INTEGER", "nullable": True},
            "group": {"type": "STRING"},
        },
        "required": ["id", "issue_id", "group"],
    },
}


@dataclass
class GroupInput:
    id: int
    title: str
    place: str | None
    category: str


def group(llm: GeminiClient, new: list[GroupInput], existing: list[GroupInput]) -> dict[int, tuple[int | None, str]]:
    """새 기사 id → (붙일 기존 이슈 id 또는 None, 새 사건 그룹 이름)."""
    prompt = GROUP_PROMPT.format(
        issues=json.dumps([{"issue_id": i.id, "title": i.title, "place": i.place, "category": i.category} for i in existing],
                          ensure_ascii=False),
        articles=json.dumps([{"id": a.id, "title": a.title, "place": a.place, "category": a.category} for a in new],
                            ensure_ascii=False),
    )
    existing_ids = {i.id for i in existing}
    new_ids = {a.id for a in new}
    result = {}
    for row in llm.generate_json(prompt, GROUP_SCHEMA):
        if row.get("id") not in new_ids:
            continue
        issue_id = row.get("issue_id")
        result[row["id"]] = (issue_id if issue_id in existing_ids else None, str(row.get("group") or row["id"]))
    return result


SUMMARY_PROMPT = """아래는 같은 사건을 다룬 기사들이다 (오래된 순). 이 사건의 현재 상황을 2문장 이내로 요약해라.
기사에 없는 내용(추측, 원인 단정, 숫자)을 추가하지 말고, 사람 이름·연락처는 넣지 마라.

사건: {title}
기사:
{articles}"""

SUMMARY_SCHEMA = {"type": "OBJECT", "properties": {"summary": {"type": "STRING"}}, "required": ["summary"]}


def summarize(llm: GeminiClient, title: str, articles: list[tuple[str, str, str]]) -> str:
    """articles: (게시 시각, 제목, 요약) 오래된 순"""
    lines = "\n".join(f"- [{t}] {title_} — {desc[:200]}" for t, title_, desc in articles)
    return str(llm.generate_json(SUMMARY_PROMPT.format(title=title, articles=lines), SUMMARY_SCHEMA)["summary"]).strip()
