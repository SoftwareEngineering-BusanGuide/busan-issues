"""긴급재난문자·기상특보 제공자 (FR-007, API-007).

재난문자는 공공누리 제4유형(출처표시·변경금지)이라 message는 받은 그대로 둔다.
"""

from datetime import datetime, timedelta, timezone
from typing import Protocol

import httpx

from app.cache import StaleCache
from app.schemas import AlertOut

KST = timezone(timedelta(hours=9))
SAFETY_DATA_URL = "https://www.safetydata.go.kr/V2/api/DSSP-IF-00247"
LIVE_SOURCE = "행정안전부 긴급재난문자 (재난안전데이터공유플랫폼, 공공누리 제4유형)"


class AlertProvider(Protocol):
    def list_alerts(self, district: str | None = None) -> list[AlertOut]: ...


def _filter_and_sort(alerts: list[AlertOut], district: str | None) -> list[AlertOut]:
    if district:
        # 수신 지역이 비어 있는 문자는 부산 전체 대상이라 모든 구·군에 포함한다
        alerts = [a for a in alerts if not a.districts or district in a.districts]
    return sorted(alerts, key=lambda a: a.issued_at, reverse=True)


def _region_label(districts: list[str]) -> str:
    return "부산 " + ", ".join(districts) if districts else "부산 전체"


class SafetyDataAlertProvider:
    """재난안전데이터공유플랫폼의 긴급재난문자 API. 최근 며칠의 부산 문자를 1분 캐시한다."""

    def __init__(self, api_key: str, client: httpx.Client | None = None, days: int = 3, limit: int = 20):
        self._api_key = api_key
        self._client = client or httpx.Client(timeout=10)
        self._days = days
        self._limit = limit
        self._cache: StaleCache[list[AlertOut]] = StaleCache(ttl_seconds=60)

    def list_alerts(self, district: str | None = None) -> list[AlertOut]:
        return _filter_and_sort(self._cache.get("busan", self._fetch), district)

    def _fetch(self) -> list[AlertOut]:
        since = datetime.now(KST) - timedelta(days=self._days)
        res = self._client.get(SAFETY_DATA_URL, params={
            "serviceKey": self._api_key,
            "returnType": "json",
            "pageNo": 1,
            "numOfRows": 100,
            "crtDt": since.strftime("%Y%m%d"),
            "rgnNm": "부산광역시",
        })
        res.raise_for_status()
        data = res.json()
        header = data.get("header") or {}
        if header.get("resultCode") != "00":
            raise RuntimeError(f"재난문자 API 오류: {header.get('resultMsg') or header.get('errorMsg')}")

        alerts: dict[str, AlertOut] = {}
        for item in data.get("body") or []:
            alert = parse_alert(item)
            if alert and alert.issued_at >= since:
                alerts[alert.id] = alert  # 일련번호(SN)로 중복 제거
        return sorted(alerts.values(), key=lambda a: a.issued_at, reverse=True)[: self._limit]


def parse_alert(item: dict) -> AlertOut | None:
    """API 항목 하나를 AlertOut으로. 부산 문자가 아니거나 형식이 틀리면 None."""
    regions = [r.strip() for r in str(item.get("RCPTN_RGN_NM") or "").split(",") if r.strip()]
    busan = [r for r in regions if r.startswith("부산광역시")]
    if not busan:
        return None
    districts = sorted({r.removeprefix("부산광역시").strip() for r in busan} - {""})
    if any(r.strip() == "부산광역시" for r in busan):
        districts = []  # 부산 전체 대상
    try:
        issued_at = datetime.strptime(str(item["CRT_DT"]), "%Y/%m/%d %H:%M:%S").replace(tzinfo=KST)
    except (KeyError, ValueError):
        return None
    return AlertOut(
        id=str(item.get("SN")),
        sender=_region_label(districts),
        message=str(item.get("MSG_CN") or ""),
        issued_at=issued_at,
        districts=districts,
        level=str(item.get("EMRG_STEP_NM") or ""),
        hazard=str(item.get("DST_SE_NM") or ""),
        source=LIVE_SOURCE,
    )
