"""
routers/analytics.py — Placeholder analytics endpoints.
All endpoints return 501 Not Implemented until Phase 1.
"""
from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()


@router.get("/sales", summary="Sales analytics")
def get_sales_analytics():
    """
    GET /analytics/sales
    TODO: Return daily/weekly/monthly sales aggregates.
    """
    return JSONResponse(
        status_code=501,
        content={"detail": "Not implemented — Phase 1"},
    )


@router.get("/sales/top-books", summary="Top selling books")
def get_top_books():
    """
    GET /analytics/sales/top-books
    TODO: Return top N books by revenue and units sold.
    """
    return JSONResponse(
        status_code=501,
        content={"detail": "Not implemented — Phase 1"},
    )


@router.get("/traffic", summary="Site traffic analytics")
def get_traffic():
    """
    GET /analytics/traffic
    TODO: Return page view counts, unique visitors, session data.
    """
    return JSONResponse(
        status_code=501,
        content={"detail": "Not implemented — Phase 1"},
    )


@router.get("/customers", summary="Customer analytics")
def get_customer_analytics():
    """
    GET /analytics/customers
    TODO: Return new vs returning customers, LTV, churn.
    """
    return JSONResponse(
        status_code=501,
        content={"detail": "Not implemented — Phase 1"},
    )
