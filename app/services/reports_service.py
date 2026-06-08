"""
services/reports_service.py — Placeholder report generation logic.
TODO: Implement CSV/PDF export and scheduled report delivery.
"""


class ReportsService:
    def __init__(self, db):
        self.db = db

    def generate_inventory_report(self):
        """TODO: Pull stock data from Django inventory API and build report."""
        raise NotImplementedError("Phase 1 — inventory report not implemented")

    def generate_sales_report(self, date_from=None, date_to=None):
        """TODO: Aggregate sale_events into a formatted report."""
        raise NotImplementedError("Phase 1 — sales report not implemented")

    def generate_customer_report(self, date_from=None, date_to=None):
        """TODO: Calculate customer LTV, retention, and churn metrics."""
        raise NotImplementedError("Phase 1 — customer report not implemented")
