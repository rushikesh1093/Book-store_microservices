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


@router.get("/summary", response_model=SalesSummary)
async def sales_summary(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    return await SalesService(db).summary(start_date, end_date)


@router.get("/daily", response_model=List[TimeSeriesPoint])
async def sales_daily(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    return await SalesService(db).daily(start_date, end_date)


@router.get("/monthly", response_model=List[TimeSeriesPoint])
async def sales_monthly(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    return await SalesService(db).monthly(start_date, end_date)


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
