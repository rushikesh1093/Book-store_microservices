"""
app/models/events.py

Analytics-owned SQLAlchemy tables. These live in the same PostgreSQL database
as the Django app but are created and managed by this microservice. They are
prefixed ``analytics_`` to avoid clashing with Django-managed tables.

  * AnalyticsEvent   -> raw events consumed from Redis pub/sub.
  * EventAggregate   -> rolled-up daily counters (filled by the scheduler).
  * ReportJob        -> metadata for generated PDF/CSV/Excel reports.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


class AnalyticsEvent(Base):
    """A single event received from the Redis event stream."""

    __tablename__ = "analytics_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    book_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    # JSON-encoded payload (kept as text for portability).
    payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True
    )


class EventAggregate(Base):
    """Daily rollup of event counts per type (built by the scheduler)."""

    __tablename__ = "analytics_event_aggregates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    bucket_date: Mapped[str] = mapped_column(String(10), index=True)  # YYYY-MM-DD
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )


class ReportJob(Base):
    """Metadata for a generated report file."""

    __tablename__ = "analytics_report_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    report_type: Mapped[str] = mapped_column(String(32))   # sales | inventory | customers
    file_format: Mapped[str] = mapped_column(String(8))    # pdf | csv | xlsx
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending|ready|failed
    file_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    file_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    params: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON of request params
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
