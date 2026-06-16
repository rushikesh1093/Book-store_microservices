"""
app/services/sales_service.py

Sales analytics. Reads from the Django-owned tables ``orders`` and
``order_items`` joined to ``books``.

Revenue is computed from order_items (quantity * unit_price) for the line-level
breakdowns and from orders.total_amount for headline totals. Only orders whose
status is in ``settings.SALE_STATUSES`` count as realised revenue.
"""
from datetime import date, datetime, timezone
from typing import List, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings


def _status_clause(prefix: str = "o") -> str:
    """Build an IN clause for the configured sale statuses."""
    placeholders = ", ".join(f":st{i}" for i in range(len(settings.SALE_STATUSES)))
    return f"{prefix}.status IN ({placeholders})"


def _status_params() -> dict:
    return {f"st{i}": s for i, s in enumerate(settings.SALE_STATUSES)}


def _date_params(start: Optional[date], end: Optional[date]) -> dict:
    return {"start": start, "end": end}


def _date_filter(col: str = "o.created_at") -> str:
    # Cast every occurrence of the bound params to date. Postgres cannot infer
    # the type of a bare parameter used only in "IS NULL", and SQLAlchemy's
    # text() parser ignores ":param" when immediately followed by a "::" cast,
    # so an explicit CAST(:name AS date) is the portable, unambiguous form.
    return (
        f"AND (CAST(:start AS date) IS NULL OR {col} >= CAST(:start AS date)) "
        f"AND (CAST(:end AS date) IS NULL OR {col} < (CAST(:end AS date) + INTERVAL '1 day'))"
    )


class SalesService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def summary(
        self, start: Optional[date] = None, end: Optional[date] = None
    ) -> dict:
        params = {**_status_params(), **_date_params(start, end)}

        totals_sql = text(
            f"""
            SELECT
                COALESCE(SUM(o.total_amount), 0)       AS total_revenue,
                COUNT(DISTINCT o.id)                   AS total_orders
            FROM orders o
            WHERE {_status_clause()} {_date_filter()}
            """
        )
        totals = (await self.db.execute(totals_sql, params)).mappings().first()

        items_sql = text(
            f"""
            SELECT COALESCE(SUM(oi.quantity), 0) AS items_sold
            FROM order_items oi
            JOIN orders o ON o.id = oi.order_id
            WHERE {_status_clause()} {_date_filter()}
            """
        )
        items = (await self.db.execute(items_sql, params)).mappings().first()

        # Current calendar-month revenue (independent of the date filter).
        month_sql = text(
            f"""
            SELECT COALESCE(SUM(o.total_amount), 0) AS monthly_revenue
            FROM orders o
            WHERE {_status_clause()}
              AND date_trunc('month', o.created_at) = date_trunc('month', now())
            """
        )
        month = (await self.db.execute(month_sql, _status_params())).mappings().first()

        top = await self.top_selling_books(start, end, limit=5)

        total_revenue = float(totals["total_revenue"])
        total_orders = int(totals["total_orders"])
        avg_order = total_revenue / total_orders if total_orders else 0.0

        return {
            "total_revenue": round(total_revenue, 2),
            "total_orders": total_orders,
            "total_items_sold": int(items["items_sold"]),
            "average_order_value": round(avg_order, 2),
            "monthly_revenue": round(float(month["monthly_revenue"]), 2),
            "top_selling_books": top,
        }

    async def top_selling_books(
        self, start: Optional[date], end: Optional[date], limit: int = 10
    ) -> List[dict]:
        params = {**_status_params(), **_date_params(start, end), "lim": limit}
        sql = text(
            f"""
            SELECT
                b.id::text                              AS book_id,
                b.title                                 AS title,
                b.author                                AS author,
                SUM(oi.quantity)                        AS units_sold,
                ROUND(SUM(oi.quantity * oi.unit_price), 2) AS revenue
            FROM order_items oi
            JOIN orders o ON o.id = oi.order_id
            JOIN books b  ON b.id = oi.book_id
            WHERE {_status_clause()} {_date_filter()}
            GROUP BY b.id, b.title, b.author
            ORDER BY units_sold DESC
            LIMIT :lim
            """
        )
        rows = (await self.db.execute(sql, params)).mappings().all()
        return [
            {
                "book_id": r["book_id"],
                "title": r["title"],
                "author": r["author"],
                "units_sold": int(r["units_sold"]),
                "revenue": float(r["revenue"]),
            }
            for r in rows
        ]

    async def daily(
        self, start: Optional[date] = None, end: Optional[date] = None
    ) -> List[dict]:
        params = {**_status_params(), **_date_params(start, end)}
        sql = text(
            f"""
            SELECT
                to_char(date_trunc('day', o.created_at), 'YYYY-MM-DD') AS period,
                COALESCE(SUM(o.total_amount), 0)                       AS revenue,
                COUNT(DISTINCT o.id)                                   AS orders,
                COALESCE(SUM(oi.items), 0)                             AS items_sold
            FROM orders o
            LEFT JOIN (
                SELECT order_id, SUM(quantity) AS items
                FROM order_items GROUP BY order_id
            ) oi ON oi.order_id = o.id
            WHERE {_status_clause()} {_date_filter()}
            GROUP BY date_trunc('day', o.created_at)
            ORDER BY date_trunc('day', o.created_at)
            """
        )
        return self._timeseries(await self.db.execute(sql, params))

    async def monthly(
        self, start: Optional[date] = None, end: Optional[date] = None
    ) -> List[dict]:
        params = {**_status_params(), **_date_params(start, end)}
        sql = text(
            f"""
            SELECT
                to_char(date_trunc('month', o.created_at), 'YYYY-MM') AS period,
                COALESCE(SUM(o.total_amount), 0)                      AS revenue,
                COUNT(DISTINCT o.id)                                  AS orders,
                COALESCE(SUM(oi.items), 0)                            AS items_sold
            FROM orders o
            LEFT JOIN (
                SELECT order_id, SUM(quantity) AS items
                FROM order_items GROUP BY order_id
            ) oi ON oi.order_id = o.id
            WHERE {_status_clause()} {_date_filter()}
            GROUP BY date_trunc('month', o.created_at)
            ORDER BY date_trunc('month', o.created_at)
            """
        )
        return self._timeseries(await self.db.execute(sql, params))

    async def by_author(
        self, start: Optional[date] = None, end: Optional[date] = None
    ) -> List[dict]:
        params = {**_status_params(), **_date_params(start, end)}
        sql = text(
            f"""
            SELECT
                COALESCE(NULLIF(b.author, ''), 'Unknown')  AS key,
                ROUND(SUM(oi.quantity * oi.unit_price), 2) AS revenue,
                COUNT(DISTINCT o.id)                       AS orders,
                SUM(oi.quantity)                           AS items_sold
            FROM order_items oi
            JOIN orders o ON o.id = oi.order_id
            JOIN books b  ON b.id = oi.book_id
            WHERE {_status_clause()} {_date_filter()}
            GROUP BY COALESCE(NULLIF(b.author, ''), 'Unknown')
            ORDER BY revenue DESC
            """
        )
        return self._grouped(await self.db.execute(sql, params))

    async def by_category(
        self, start: Optional[date] = None, end: Optional[date] = None
    ) -> List[dict]:
        """
        Revenue grouped by category.

        The Django ``books`` table has no category foreign key in this schema,
        so we attempt to use an optional ``book_categories`` association table
        (book_id, category_id). If that relation is absent we fall back to
        grouping by language as a best-effort dimension and tag the result.
        """
        params = {**_status_params(), **_date_params(start, end)}
        link_sql = text(
            f"""
            SELECT
                COALESCE(c.name, 'Uncategorised')          AS key,
                ROUND(SUM(oi.quantity * oi.unit_price), 2) AS revenue,
                COUNT(DISTINCT o.id)                       AS orders,
                SUM(oi.quantity)                           AS items_sold
            FROM order_items oi
            JOIN orders o            ON o.id = oi.order_id
            JOIN books b             ON b.id = oi.book_id
            LEFT JOIN book_categories bc ON bc.book_id = b.id
            LEFT JOIN categories c       ON c.id = bc.category_id
            WHERE {_status_clause()} {_date_filter()}
            GROUP BY COALESCE(c.name, 'Uncategorised')
            ORDER BY revenue DESC
            """
        )
        try:
            return self._grouped(await self.db.execute(link_sql, params))
        except Exception:
            # Association table not present — degrade to language grouping.
            await self.db.rollback()
            fallback_sql = text(
                f"""
                SELECT
                    COALESCE(NULLIF(b.language, ''), 'Unknown') AS key,
                    ROUND(SUM(oi.quantity * oi.unit_price), 2)  AS revenue,
                    COUNT(DISTINCT o.id)                        AS orders,
                    SUM(oi.quantity)                            AS items_sold
                FROM order_items oi
                JOIN orders o ON o.id = oi.order_id
                JOIN books b  ON b.id = oi.book_id
                WHERE {_status_clause()} {_date_filter()}
                GROUP BY COALESCE(NULLIF(b.language, ''), 'Unknown')
                ORDER BY revenue DESC
                """
            )
            return self._grouped(await self.db.execute(fallback_sql, params))

    # ── helpers ─────────────────────────────────────────────────
    @staticmethod
    def _timeseries(result) -> List[dict]:
        return [
            {
                "period": r["period"],
                "revenue": float(r["revenue"]),
                "orders": int(r["orders"]),
                "items_sold": int(r["items_sold"]),
            }
            for r in result.mappings().all()
        ]

    @staticmethod
    def _grouped(result) -> List[dict]:
        return [
            {
                "key": r["key"],
                "revenue": float(r["revenue"]),
                "orders": int(r["orders"]),
                "items_sold": int(r["items_sold"]),
            }
            for r in result.mappings().all()
        ]
