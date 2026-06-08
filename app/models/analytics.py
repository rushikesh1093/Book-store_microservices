"""
models/analytics.py — SQLAlchemy ORM models for analytics data.
TODO: Implement event sourcing tables for pageviews, clicks, conversions.
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, DateTime, Boolean, Text
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class SaleEvent(Base):
    """
    Placeholder: records each individual sale event.
    TODO: Populate from Django order webhooks or Celery tasks.
    """
    __tablename__ = "sale_events"

    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id     = Column(String(36), nullable=False, index=True)
    book_id      = Column(String(36), nullable=False, index=True)
    quantity     = Column(Integer, default=1)
    unit_price   = Column(Float, default=0.0)
    revenue      = Column(Float, default=0.0)
    currency     = Column(String(3), default='USD')
    sold_at      = Column(DateTime, default=datetime.utcnow, index=True)
    # TODO: Add category_id, author_id, customer_segment


class PageViewEvent(Base):
    """
    Placeholder: records each page view event.
    TODO: Ingest from Django analytics app or frontend beacon.
    """
    __tablename__ = "pageview_events"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    path       = Column(String(500), nullable=False, index=True)
    user_id    = Column(String(36), nullable=True, index=True)
    session_id = Column(String(100), nullable=True)
    ip_address = Column(String(45), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
