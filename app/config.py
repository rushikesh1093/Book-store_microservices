"""
app/config.py

Centralised settings for the Analytics microservice.

Reads from environment variables (and an optional .env file). The service is
designed to share the same PostgreSQL database and Redis instance as the Django
backend, so DATABASE_URL / REDIS_URL mirror the values used there.
"""
from functools import lru_cache
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _clean(value: str) -> str:
    """Strip surrounding whitespace and matching quotes from a value.

    Platforms like Render store env vars literally, so a value pasted as
    DATABASE_URL="postgresql://..." keeps the quotes and breaks URL parsing.
    """
    if not isinstance(value, str):
        return value
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        value = value[1:-1].strip()
    return value


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ── Service metadata ────────────────────────────────────────
    SERVICE_NAME: str = "bookstore-analytics"
    VERSION: str = "1.0.0"
    DEBUG: bool = False

    # ── Database (shared Neon PostgreSQL) ───────────────────────
    # Standard libpq URL, e.g.
    #   postgresql://user:pass@host/db?sslmode=require&channel_binding=require
    DATABASE_URL: str = ""

    # ── Redis (shared instance) ─────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379"

    @field_validator("DATABASE_URL", "REDIS_URL", mode="before")
    @classmethod
    def _strip_quotes(cls, v):
        return _clean(v)

    # ── Redis event channels we subscribe to ───────────────────
    EVENT_CHANNELS: List[str] = [
        "order_created",
        "book_viewed",
        "search_query",
        "recommendation_clicked",
    ]

    # ── Scheduler toggle (disable in tests) ─────────────────────
    SCHEDULER_ENABLED: bool = True

    # ── Redis consumer toggle ───────────────────────────────────
    REDIS_CONSUMER_ENABLED: bool = True

    # ── Where generated reports are written ─────────────────────
    REPORTS_DIR: str = "generated_reports"

    # ── CORS ────────────────────────────────────────────────────
    CORS_ORIGINS: List[str] = ["*"]

    # ── Business rules ──────────────────────────────────────────
    # Order statuses that count as realised revenue / a "sale".
    SALE_STATUSES: List[str] = ["confirmed", "processing", "shipped", "delivered"]
    # Days without an order before a customer is flagged churn-risk.
    CHURN_RISK_DAYS: int = 90
    # Window (days) used to classify a book as a slow mover.
    SLOW_MOVER_DAYS: int = 90

    @property
    def async_database_url(self) -> str:
        """SQLAlchemy async URL using the psycopg3 driver."""
        return self._with_driver(self.DATABASE_URL, "postgresql+psycopg")

    @property
    def sync_database_url(self) -> str:
        """SQLAlchemy sync URL (used by pandas / report generation)."""
        return self._with_driver(self.DATABASE_URL, "postgresql+psycopg")

    @staticmethod
    def _with_driver(url: str, driver: str) -> str:
        if not url:
            return url
        # Normalise the scheme to the requested SQLAlchemy driver.
        for prefix in ("postgresql+psycopg://", "postgresql+asyncpg://",
                       "postgresql://", "postgres://"):
            if url.startswith(prefix):
                return f"{driver}://" + url[len(prefix):]
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
