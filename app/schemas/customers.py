"""
schemas/customers.py — Pydantic schemas for customer analytics.
TODO: Implement once customer data pipeline is built.
"""
from pydantic import BaseModel
from datetime import date
from typing import Optional


class CustomerSummary(BaseModel):
    """Placeholder: customer analytics summary."""
    total_customers:     int   = 0
    new_customers:       int   = 0
    returning_customers: int   = 0
    avg_lifetime_value:  float = 0.0
    # TODO: Add churn_rate, top_segments


class CustomerFilter(BaseModel):
    """Query filter for customer reports."""
    date_from: Optional[date] = None
    date_to:   Optional[date] = None
