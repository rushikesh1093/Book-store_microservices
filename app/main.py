"""
main.py — FastAPI application entrypoint.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routers import health, analytics, reports

app = FastAPI(
    title="Enterprise Book Store — Analytics Microservice",
    description="Sales analytics, inventory reports, and customer insights.",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(health.router,    tags=["Health"])
app.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])
app.include_router(reports.router,   prefix="/reports",   tags=["Reports"])
