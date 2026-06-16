"""
app/routers/health.py

Liveness / readiness probe. Checks PostgreSQL and Redis connectivity and
reports overall service status.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Response, status

from app.config import settings
from app.database import check_database
from app.models.schemas import DependencyStatus, HealthResponse
from app.redis_client import check_redis

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health(response: Response) -> HealthResponse:
    db_ok = await check_database()
    redis_ok = await check_redis()
    healthy = db_ok and redis_ok

    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return HealthResponse(
        service=settings.SERVICE_NAME,
        version=settings.VERSION,
        status="healthy" if healthy else "degraded",
        dependencies=[
            DependencyStatus(name="postgresql", status="up" if db_ok else "down"),
            DependencyStatus(name="redis", status="up" if redis_ok else "down"),
        ],
        timestamp=datetime.now(timezone.utc),
    )
