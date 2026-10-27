from fastapi import APIRouter, Query, Request

from app.schemas import AlertOut

router = APIRouter(tags=["alerts"])


@router.get("/alerts", response_model=list[AlertOut])
def alerts(request: Request, district: str | None = Query(None, description="구·군 이름 (예: 사하구)")) -> list[AlertOut]:
    """API-007 재난문자·기상특보 원문 (FR-007)."""
    return request.app.state.alert_provider.list_alerts(district)
