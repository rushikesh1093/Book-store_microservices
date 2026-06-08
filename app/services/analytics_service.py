"""
services/analytics_service.py — Placeholder analytics business logic.
TODO: Implement queries against sale_events and pageview_events tables.
"""


class AnalyticsService:
    def __init__(self, db):
        self.db = db

    def get_sales_summary(self, date_from=None, date_to=None):
        """
        TODO: Query SaleEvent and aggregate by period.
        """
        raise NotImplementedError("Phase 1 — sales summary not implemented")

    def get_top_books(self, limit=10):
        """
        TODO: Query SaleEvent, group by book_id, order by revenue DESC.
        """
        raise NotImplementedError("Phase 1 — top books not implemented")

    def get_traffic_summary(self, date_from=None, date_to=None):
        """
        TODO: Query PageViewEvent, aggregate unique visitors and sessions.
        """
        raise NotImplementedError("Phase 1 — traffic summary not implemented")
