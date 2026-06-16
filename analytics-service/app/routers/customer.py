"""
app/routers/customer.py

Customer analytics endpoints.
  GET /analytics/customers/cohorts
  GET /analytics/customers/ltv
  GET /analytics/customers/acquisition
  GET /analytics/customers/churn-risk
"""
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.schemas import (
    AcquisitionPoint,
    ChurnRiskCustomer,
    LTVResponse,
)
from app.services.customer_service import CustomerService

router = APIRouter(prefix="/analytics/customers", tags=["customers"])


@router.get("/cohorts")
async def customer_cohorts(
    months: int = Query(12, ge=1, le=36),
    db: AsyncSession = Depends(get_db),
):
    return await CustomerService(db).cohorts(months=months)


@router.get("/ltv", response_model=LTVResponse)
async def customer_ltv(
    limit: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    return await CustomerService(db).ltv(limit=limit)


@router.get("/acquisition", response_model=List[AcquisitionPoint])
async def customer_acquisition(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    return await CustomerService(db).acquisition(start_date, end_date)


@router.get("/churn-risk", response_model=List[ChurnRiskCustomer])
async def customer_churn_risk(
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    return await CustomerService(db).churn_risk(limit=limit)
