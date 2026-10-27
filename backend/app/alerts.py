"""긴급재난문자·기상특보 제공자 (FR-007).

v0.1은 데모 문자를 돌려준다. 공공데이터포털 API 키를 받으면 같은 인터페이스로 실제 제공자를 추가하고
create_app에서 바꿔 끼운다. 재난문자는 공공누리 제4유형(변경금지)이라 message를 가공하지 않는다.
"""

from datetime import datetime, timedelta, timezone
from typing import Protocol

from app.schemas import AlertOut

DEMO_SOURCE = "행정안전부 긴급재난문자 (데모 데이터)"


class AlertProvider(Protocol):
    def list_alerts(self, district: str | None = None) -> list[AlertOut]: ...


class DemoAlertProvider:
    def list_alerts(self, district: str | None = None) -> list[AlertOut]:
        now = datetime.now(timezone.utc)
        alerts = [
            AlertOut(
                id="demo-1",
                sender="부산광역시 사하구",
                message="[사하구] 하단동 낙동대로 인근 도로 침하로 차로 2개를 통제 중입니다. 차량은 우회하시고 보행자는 접근을 자제해 주시기 바랍니다.",
                issued_at=now - timedelta(hours=3),
                districts=["사하구"],
                source=DEMO_SOURCE,
            ),
            AlertOut(
                id="demo-2",
                sender="기상청",
                message="[기상청] 부산 해운대구·수영구 강풍주의보 발효. 해안가 접근과 야외 활동을 자제해 주시기 바랍니다.",
                issued_at=now - timedelta(minutes=95),
                districts=["해운대구", "수영구"],
                source=DEMO_SOURCE,
            ),
            AlertOut(
                id="demo-3",
                sender="부산광역시",
                message="[부산광역시] 오늘 오후 연제구 중앙대로 일대 행사로 교통이 통제됩니다. 대중교통을 이용해 주시기 바랍니다.",
                issued_at=now - timedelta(minutes=30),
                districts=["연제구"],
                source=DEMO_SOURCE,
            ),
        ]
        if district:
            alerts = [a for a in alerts if district in a.districts]
        return sorted(alerts, key=lambda a: a.issued_at, reverse=True)
