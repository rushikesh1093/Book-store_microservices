"""
app/routers/health.py

Liveness / readiness probe. Checks PostgreSQL connectivity — the only critical
dependency for serving analytics. (Redis is optional and not used by default,
so it is not part of the health check.)
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Response, status

from app.config import settings
from app.database import check_database
from app.models.schemas import DependencyStatus, HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health(response: Response) -> HealthResponse:
    db_ok = await check_database()
    if not db_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return HealthResponse(
        service=settings.SERVICE_NAME,
        version=settings.VERSION,
        status="healthy" if db_ok else "unhealthy",
        dependencies=[
            DependencyStatus(name="postgresql", status="up" if db_ok else "down"),
        ],
        timestamp=datetime.now(timezone.utc),
    )
