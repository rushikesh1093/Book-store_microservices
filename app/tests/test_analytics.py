"""
tests/test_analytics.py — Analytics endpoint placeholder tests.
"""
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_sales_analytics_returns_501():
    """GET /analytics/sales should return 501 Not Implemented."""
    response = client.get("/analytics/sales")
    assert response.status_code == 501


def test_top_books_returns_501():
    response = client.get("/analytics/sales/top-books")
    assert response.status_code == 501


def test_traffic_returns_501():
    response = client.get("/analytics/traffic")
    assert response.status_code == 501


def test_customer_analytics_returns_501():
    response = client.get("/analytics/customers")
    assert response.status_code == 501


# TODO: Add integration tests once analytics data pipeline is implemented
