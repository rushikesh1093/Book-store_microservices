"""
app/routers/inventory.py

Inventory analytics endpoints.
  GET /analytics/inventory/health
  GET /analytics/inventory/turnover
  GET /analytics/inventory/slow-movers
  GET /analytics/inventory/reorder-forecast
"""
from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.schemas import InventoryHealth, ReorderItem, TurnoverItem
from app.services.inventory_service import InventoryService

router = APIRouter(prefix="/analytics/inventory", tags=["inventory"])


@router.get("/health", response_model=InventoryHealth)
async def inventory_health(db: AsyncSession = Depends(get_db)):
    return await InventoryService(db).health()


@router.get("/turnover", response_model=List[TurnoverItem])
async def inventory_turnover(
    days: int = Query(90, ge=1, le=365),
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    return await InventoryService(db).turnover(days=days, limit=limit)


@router.get("/slow-movers")
async def inventory_slow_movers(
    days: int = Query(90, ge=1, le=365),
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    return await InventoryService(db).slow_movers(days=days, limit=limit)


@router.get("/reorder-forecast", response_model=List[ReorderItem])
async def inventory_reorder_forecast(
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    return await InventoryService(db).reorder_forecast(days=days, limit=limit)
