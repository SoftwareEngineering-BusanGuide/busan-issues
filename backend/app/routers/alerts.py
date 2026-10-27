from fastapi import APIRouter, HTTPException, Query, Request

from app.cache import DataUnavailable
from app.schemas import AlertOut

router = APIRouter(tags=["alerts"])


@router.get("/alerts", response_model=list[AlertOut])
def alerts(request: Request, district: str | None = Query(None, description="구·군 이름 (예: 사하구)")) -> list[AlertOut]:
    """API-007 재난문자·기상특보 원문 (FR-007). 실시간 문자를 못 받으면 데모로 대신하지 않고 503을 준다."""
    try:
        return request.app.state.alert_provider.list_alerts(district)
    except DataUnavailable:
        raise HTTPException(status_code=503, detail="실시간 재난문자를 일시적으로 불러올 수 없습니다.")
