"""
app/main.py

FastAPI Analytics Microservice — application entrypoint.

Wires together routers, database initialisation, the Redis event consumer and
the APScheduler ETL jobs via the lifespan context manager.
"""
import asyncio
import logging
import sys
from contextlib import asynccontextmanager

# psycopg's async driver cannot run on Windows' default ProactorEventLoop.
# Switch to the selector loop policy before any event loop is created.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import async_engine, init_models
from app.redis_client import close_redis
from app.routers import customer, exports, health, inventory, reports, sales
from app.scheduler.jobs import shutdown_scheduler, start_scheduler
from app.services.redis_consumer import consumer

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("analytics")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting %s v%s", settings.SERVICE_NAME, settings.VERSION)

    # Ensure analytics-owned tables exist.
    try:
        await init_models()
    except Exception:
        logger.exception("Failed to initialise analytics tables (continuing).")

    # Start the Redis event consumer.
    if settings.REDIS_CONSUMER_ENABLED:
        try:
            await consumer.start()
        except Exception:
            logger.exception("Failed to start Redis consumer.")

    # Start scheduled ETL jobs.
    if settings.SCHEDULER_ENABLED:
        try:
            start_scheduler()
        except Exception:
            logger.exception("Failed to start scheduler.")

    yield

    # ── Shutdown ────────────────────────────────────────────────
    logger.info("Shutting down %s", settings.SERVICE_NAME)
    if settings.SCHEDULER_ENABLED:
        shutdown_scheduler()
    if settings.REDIS_CONSUMER_ENABLED:
        await consumer.stop()
    await close_redis()
    await async_engine.dispose()


app = FastAPI(
    title="Enterprise Book Store — Analytics Service",
    description=(
        "FastAPI analytics microservice providing sales, inventory and customer "
        "analytics, report generation (PDF/CSV/Excel), Redis event processing "
        "and scheduled ETL jobs. Independent of the Django backend; reads from "
        "the shared PostgreSQL database."
    ),
    version=settings.VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ────────────────────────────────────────────────────
app.include_router(health.router)
app.include_router(sales.router)
app.include_router(inventory.router)
app.include_router(customer.router)
app.include_router(reports.router)
app.include_router(exports.router)


@app.get("/", tags=["root"])
async def root():
    return {
        "service": settings.SERVICE_NAME,
        "version": settings.VERSION,
        "docs": "/docs",
        "health": "/health",
    }
