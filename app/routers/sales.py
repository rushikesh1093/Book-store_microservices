"""
app/routers/sales.py

Sales analytics endpoints.
  GET /analytics/sales/summary
  GET /analytics/sales/daily
  GET /analytics/sales/monthly
  GET /analytics/sales/by-category
  GET /analytics/sales/by-author
"""
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.schemas import GroupedRevenue, SalesSummary, TimeSeriesPoint
from app.services.sales_service import SalesService

router = APIRouter(prefix="/analytics/sales", tags=["sales"])


def _parse_book_ids(book_ids: Optional[str]) -> Optional[List[str]]:
    """Split a comma-separated ``book_ids`` query param into a clean list.

    Returns None when nothing usable is supplied so services fall back to the
    unscoped (store-wide) queries.
    """
    if not book_ids:
        return None
    ids = [b.strip() for b in book_ids.split(",") if b.strip()]
    return ids or None


@router.get("", response_model=SalesSummary)
@router.get("/", response_model=SalesSummary)
async def sales_index(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    book_ids: Optional[str] = Query(
        None, description="Comma-separated book UUIDs to scope the summary to."
    ),
    db: AsyncSession = Depends(get_db),
):
    """Sales index — returns the headline summary (alias of /summary)."""
    return await SalesService(db).summary(
        start_date, end_date, book_ids=_parse_book_ids(book_ids)
    )


@router.get("/summary", response_model=SalesSummary)
async def sales_summary(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    book_ids: Optional[str] = Query(
        None, description="Comma-separated book UUIDs to scope the summary to."
    ),
    db: AsyncSession = Depends(get_db),
):
    return await SalesService(db).summary(
        start_date, end_date, book_ids=_parse_book_ids(book_ids)
    )


@router.get("/top-books")
async def sales_top_books(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    limit: int = Query(10, ge=1, le=100),
    book_ids: Optional[str] = Query(
        None, description="Comma-separated book UUIDs to scope results to."
    ),
    db: AsyncSession = Depends(get_db),
):
    """Best-selling books by units sold over the optional date range."""
    return await SalesService(db).top_selling_books(
        start_date, end_date, limit=limit, book_ids=_parse_book_ids(book_ids)
    )


@router.get("/book/{book_id}")
async def sales_for_book(
    book_id: str,
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Sales performance for a single book (totals + daily series)."""
    return await SalesService(db).book_performance(book_id, start_date, end_date)


@router.get("/daily", response_model=List[TimeSeriesPoint])
async def sales_daily(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    book_ids: Optional[str] = Query(
        None, description="Comma-separated book UUIDs to scope the series to."
    ),
    db: AsyncSession = Depends(get_db),
):
    return await SalesService(db).daily(
        start_date, end_date, book_ids=_parse_book_ids(book_ids)
    )


@router.get("/monthly", response_model=List[TimeSeriesPoint])
async def sales_monthly(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    book_ids: Optional[str] = Query(
        None, description="Comma-separated book UUIDs to scope the series to."
    ),
    db: AsyncSession = Depends(get_db),
):
    return await SalesService(db).monthly(
        start_date, end_date, book_ids=_parse_book_ids(book_ids)
    )


@router.get("/by-category", response_model=List[GroupedRevenue])
async def sales_by_category(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    return await SalesService(db).by_category(start_date, end_date)


@router.get("/by-author", response_model=List[GroupedRevenue])
async def sales_by_author(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    return await SalesService(db).by_author(start_date, end_date)
