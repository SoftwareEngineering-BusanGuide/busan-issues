from datetime import datetime, timedelta, timezone

import httpx
from fastapi.testclient import TestClient

from app.alerts import LIVE_SOURCE, SafetyDataAlertProvider, parse_alert

KST = timezone(timedelta(hours=9))


def _item(sn: int, minutes_ago: int, region: str, msg: str = "문자 원문", step: str = "안전안내", kind: str = "호우") -> dict:
    t = datetime.now(KST) - timedelta(minutes=minutes_ago)
    return {"SN": sn, "CRT_DT": t.strftime("%Y/%m/%d %H:%M:%S"), "RCPTN_RGN_NM": region, "MSG_CN": msg,
            "EMRG_STEP_NM": step, "DST_SE_NM": kind}


def _provider(items: list[dict], status: int = 200, result_code: str = "00") -> SafetyDataAlertProvider:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["rgnNm"] == "부산광역시"
        return httpx.Response(status, json={"header": {"resultCode": result_code, "resultMsg": "MSG"}, "body": items})

    return SafetyDataAlertProvider("test-key", client=httpx.Client(transport=httpx.MockTransport(handler)))


def test_no_key_returns_503(client: TestClient):
    res = client.get("/api/alerts")
    assert res.status_code == 503 and "키" in res.json()["detail"]


# ── 실제 API 응답 처리 ──

def test_parse_keeps_message_and_reads_region():
    alert = parse_alert(_item(1, 10, "부산광역시 북구 ", msg="대천천 산책로를 통제하오니 출입을 금지하여 주시고"))
    assert alert.message == "대천천 산책로를 통제하오니 출입을 금지하여 주시고"  # 원문 그대로 (변경금지)
    assert alert.districts == ["북구"] and alert.sender == "부산 북구"
    assert alert.level == "안전안내" and alert.hazard == "호우" and alert.source == LIVE_SOURCE
    assert alert.issued_at.utcoffset() == timedelta(hours=9)


def test_parse_whole_city_and_rejects_other_regions():
    assert parse_alert(_item(1, 10, "부산광역시  ")).districts == []
    assert parse_alert(_item(1, 10, "부산광역시  ")).sender == "부산 전체"
    assert parse_alert(_item(1, 10, "경상남도 김해시")) is None
    assert parse_alert({"SN": 1, "CRT_DT": "형식오류", "RCPTN_RGN_NM": "부산광역시 북구"}) is None


def test_provider_sorts_dedupes_and_includes_citywide_in_district_filter():
    p = _provider([
        _item(1, 120, "부산광역시 북구 "),
        _item(2, 10, "부산광역시  "),
        _item(3, 60, "부산광역시 금정구 "),
        _item(3, 60, "부산광역시 금정구 "),  # 같은 일련번호
    ])
    assert [a.id for a in p.list_alerts()] == ["2", "3", "1"]
    # 부산 전체 문자(2)는 북구 필터에도 포함
    assert [a.id for a in p.list_alerts("북구")] == ["2", "1"]


def test_provider_drops_alerts_older_than_window():
    assert [a.id for a in _provider([_item(1, 60 * 24 * 5, "부산광역시 북구 ")]).list_alerts()] == []


def test_api_error_without_cache_returns_503(client: TestClient):
    client.app.state.alert_provider = _provider([], result_code="30")
    res = client.get("/api/alerts")
    assert res.status_code == 503
