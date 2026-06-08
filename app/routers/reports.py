"""
routers/reports.py — Placeholder report endpoints.
All endpoints return 501 Not Implemented until Phase 1.
"""
from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()


@router.get("/inventory", summary="Inventory report")
def inventory_report():
    """
    GET /reports/inventory
    TODO: Return stock levels, low stock alerts, reorder recommendations.
    """
    return JSONResponse(
        status_code=501,
        content={"detail": "Not implemented — Phase 1"},
    )


@router.get("/sales", summary="Sales report")
def sales_report():
    """
    GET /reports/sales
    TODO: Return revenue, order counts, average order value by date range.
    """
    return JSONResponse(
        status_code=501,
        content={"detail": "Not implemented — Phase 1"},
    )


@router.get("/customers", summary="Customer report")
def customer_report():
    """
    GET /reports/customers
    TODO: Return customer acquisition, retention, and segment breakdown.
    """
    return JSONResponse(
        status_code=501,
        content={"detail": "Not implemented — Phase 1"},
    )
