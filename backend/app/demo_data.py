"""v0.1 데모 데이터. 실제 사건이 아니며, 뉴스 수집 파이프라인(FR-008~010)이 붙으면 쓰지 않는다.

기사 링크는 실제 언론사로 오해되지 않도록 모두 example.com 주소를 쓴다.
"""

from datetime import datetime, timedelta

from app.constants import IMPORTANCE_HIGH as HIGH
from app.constants import IMPORTANCE_NORMAL as NORMAL
from app.models import Article, Issue

# (제목, 분류, 중요도, 장소, 위도, 경도, 상황 요약, [(기사 제목, 기사 요약, 몇 분 전)])
DEMO_ISSUES = [
    ("하단동 도로 싱크홀", "재난·안전", HIGH, "사하구 하단동 낙동대로", 35.1066, 128.9668,
     "도로 침하로 차로 2개가 통제 중이며, 구청이 원인을 조사하고 복구 작업을 하고 있다.",
     [("하단동 도로에 싱크홀 발생", "낙동대로 인근 도로가 내려앉아 차량 통행이 일부 통제됐다.", 180),
      ("싱크홀 구간 차로 2개 통제", "구청은 안전 점검을 위해 인근 차로 2개를 통제한다고 밝혔다.", 120),
      ("하단동 싱크홀 원인 조사·복구 착수", "지하 매설물 손상 여부를 조사하며 복구 작업을 시작했다.", 40)]),
    ("시청 앞 중앙대로 행사 교통 통제", "교통", HIGH, "연제구 부산시청 앞 중앙대로", 35.1792, 129.0763,
     "오후 행사로 중앙대로 일부 구간이 통제되어 버스가 우회 운행한다.",
     [("중앙대로 오후 교통 통제 예정", "시청 앞 행사로 중앙대로 일부 구간이 통제된다.", 90),
      ("시내버스 우회 운행 안내", "통제 구간을 지나는 버스 노선이 임시로 우회한다.", 30)]),
    ("해운대 강풍주의보, 해안 산책로 통제", "재난·안전", HIGH, "해운대구 해운대해수욕장", 35.1587, 129.1604,
     None,
     [("해운대·수영 강풍주의보 발효", "해안가 산책로 출입이 통제되고 야외 행사가 취소됐다.", 95)]),
    ("서면 상가 건물 화재", "사건·사고", HIGH, "부산진구 부전동 서면", 35.1578, 129.0600,
     "상가 3층에서 난 불은 진화됐고, 인근 도로 통제가 풀렸다.",
     [("서면 상가 건물에서 화재", "상가 3층에서 불이 나 소방차가 출동했다.", 70),
      ("서면 상가 화재 진화 완료", "불은 1시간 만에 꺼졌고 인명 피해는 없었다.", 25)]),
    ("연산교차로 도로 포장 공사", "공사·생활", NORMAL, "연제구 연산동 연산교차로", 35.1856, 129.0817,
     None,
     [("연산교차로 야간 포장 공사", "이번 주 밤 10시부터 다음 날 오전 6시까지 차로 일부가 통제된다.", 300)]),
    ("거제동 일부 단수 예정", "공사·생활", NORMAL, "연제구 거제동", 35.1890, 129.0700,
     None,
     [("거제동 상수도관 교체로 단수", "내일 오전 9시부터 6시간 동안 일부 지역에 물이 끊긴다.", 480)]),
    ("부산시 청년 주거 지원 확대 발표", "행정", NORMAL, "연제구 부산시청", 35.1798, 129.0750,
     None,
     [("부산시, 청년 주거 지원 확대", "청년 월세 지원 대상과 금액을 늘린다고 발표했다.", 360)]),
    ("온천장역 교차로 추돌사고", "사건·사고", NORMAL, "동래구 온천동 온천장역 교차로", 35.2205, 129.0860,
     None,
     [("온천장 교차로 차량 3대 추돌", "출근길 추돌사고로 1개 차로가 한때 통제됐다.", 50)]),
    ("광안리 해변 주말 야간 행사", "행사", NORMAL, "수영구 광안리해수욕장", 35.1532, 129.1187,
     None,
     [("광안리 해변 주말 야간 공연", "주말 저녁 해변 무대에서 공연이 열리고 일대 주차가 제한된다.", 1440)]),
    ("기장읍 일부 정전", "공사·생활", NORMAL, "기장군 기장읍 동부리", 35.2445, 129.2222,
     None,
     [("기장읍 약 300세대 정전", "선로 점검으로 정전이 발생했으며 1시간 안에 복구될 예정이다.", 140)]),
]


def build_demo_issues(now: datetime) -> list[Issue]:
    issues = []
    n = 0
    for title, category, importance, place, lat, lng, summary, articles in DEMO_ISSUES:
        issue = Issue(
            title=title,
            category=category,
            importance=importance,
            status_summary=summary,
            place_name=place,
            lat=lat,
            lng=lng,
            updated_at=now - timedelta(minutes=min(m for *_, m in articles)),
        )
        for a_title, a_desc, minutes_ago in articles:
            n += 1
            issue.articles.append(Article(
                title=a_title,
                description=a_desc,
                url=f"https://example.com/demo/news/{n}",
                published_at=now - timedelta(minutes=minutes_ago),
            ))
        issues.append(issue)
    return issues
