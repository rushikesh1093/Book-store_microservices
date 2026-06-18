"""
app/models/schemas.py

Pydantic response/request schemas for the public API. Kept intentionally
permissive (analytics payloads are read-only summaries).
"""
from datetime import date, datetime
from typing import Any, List, Optional

from pydantic import BaseModel, Field


# ── Health ─────────────────────────────────────────────────────
class DependencyStatus(BaseModel):
    name: str
    status: str  # "up" | "down"


class HealthResponse(BaseModel):
    service: str
    version: str
    status: str  # "healthy" | "degraded"
    dependencies: List[DependencyStatus]
    timestamp: datetime


# ── Sales ──────────────────────────────────────────────────────
class SalesSummary(BaseModel):
    total_revenue: float
    total_orders: int
    total_items_sold: int
    average_order_value: float
    monthly_revenue: float
    top_selling_books: List[dict] = Field(default_factory=list)


class TimeSeriesPoint(BaseModel):
    period: str
    revenue: float
    orders: int
    items_sold: int


class GroupedRevenue(BaseModel):
    key: str
    revenue: float
    orders: int
    items_sold: int


# ── Inventory ──────────────────────────────────────────────────
class InventoryHealth(BaseModel):
    total_books: int
    in_stock: int
    low_stock: int
    out_of_stock: int
    inventory_value: float
    low_stock_books: List[dict] = Field(default_factory=list)
    out_of_stock_books: List[dict] = Field(default_factory=list)


class TurnoverItem(BaseModel):
    book_id: str
    title: str
    units_sold: int
    current_stock: int
    turnover_ratio: float


class ReorderItem(BaseModel):
    book_id: str
    title: str
    current_stock: int
    reorder_level: int
    avg_daily_sales: float
    recommended_reorder_qty: int


# ── Customers ──────────────────────────────────────────────────
class LTVResponse(BaseModel):
    average_ltv: float
    median_ltv: float
    repeat_customer_rate: float
    total_customers: int
    repeat_customers: int
    top_customers: List[dict] = Field(default_factory=list)


class CohortRow(BaseModel):
    cohort_month: str
    customers: int
    retention: dict  # {month_offset: active_customers}


class AcquisitionPoint(BaseModel):
    period: str
    new_customers: int


class ChurnRiskCustomer(BaseModel):
    user_id: str
    email: str
    last_order_date: Optional[date]
    days_since_last_order: Optional[int]
    lifetime_value: float
    risk_level: str


# ── Reports ────────────────────────────────────────────────────
class ReportRequest(BaseModel):
    report_type: str = Field("sales", description="sales | inventory | customers")
    file_format: str = Field("pdf", description="pdf | csv | xlsx")
    start_date: Optional[date] = None
    end_date: Optional[date] = None


class ReportResponse(BaseModel):
    id: str
    report_type: str
    file_format: str
    status: str
    file_name: Optional[str] = None
    download_url: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
