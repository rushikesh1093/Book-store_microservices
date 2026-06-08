"""
schemas/sales.py — Pydantic schemas for sales analytics.
TODO: Implement once analytics data pipeline is built.
"""
from pydantic import BaseModel
from datetime import date
from typing import Optional


class SalesSummary(BaseModel):
    """Placeholder: daily/weekly/monthly sales summary."""
    # TODO: Add period, revenue, order_count, avg_order_value
    period:      str
    revenue:     float = 0.0
    order_count: int   = 0
    avg_order_value: float = 0.0


class TopBook(BaseModel):
    """Placeholder: top-selling book entry."""
    # TODO: Add book_id, title, units_sold, revenue
    book_id:    str
    title:      str
    units_sold: int   = 0
    revenue:    float = 0.0


class SalesFilter(BaseModel):
    """Query filter for sales reports."""
    # TODO: Add category_id, author_id filters
    date_from: Optional[date] = None
    date_to:   Optional[date] = None
    limit:     int = 10
