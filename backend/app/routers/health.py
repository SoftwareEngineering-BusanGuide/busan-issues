from typing import Literal

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db import get_session

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    database: Literal["ok", "error"]


@router.get("/health", response_model=HealthResponse)
def health(response: Response, session: Session = Depends(get_session)) -> HealthResponse:
    """API-001 서버 상태 확인. DB에 연결할 수 없으면 503을 돌려준다."""
    try:
        session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthResponse(status="degraded", database="error")
    return HealthResponse(status="ok", database="ok")
