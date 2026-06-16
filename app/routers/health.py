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

    # The database is the only critical dependency for serving analytics.
    # Redis powers event ingestion/ETL which is non-critical for liveness, so a
    # Redis outage reports "degraded" but still returns 200 — this prevents
    # platform health probes (e.g. Render) from restart-looping when Redis is
    # not provisioned. Only a database outage returns 503.
    if not db_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        overall = "unhealthy"
    elif not redis_ok:
        overall = "degraded"
    else:
        overall = "healthy"

    return HealthResponse(
        service=settings.SERVICE_NAME,
        version=settings.VERSION,
        status=overall,
        dependencies=[
            DependencyStatus(name="postgresql", status="up" if db_ok else "down"),
            DependencyStatus(name="redis", status="up" if redis_ok else "down"),
        ],
        timestamp=datetime.now(timezone.utc),
    )
