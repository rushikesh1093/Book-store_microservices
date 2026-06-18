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


def _book_clause(book_ids: Optional[List[str]], prefix: str = "oi") -> str:
    """Optional ``book_id IN (...)`` clause, scoping results to specific books.

    Returns an empty string when no ids are supplied so the surrounding query is
    unaffected. Used to scope sales to a single author's catalogue (the set of
    books they own in the Django backend) or to one individual book.
    """
    if not book_ids:
        return ""
    placeholders = ", ".join(f":bk{i}" for i in range(len(book_ids)))
    return f"AND {prefix}.book_id IN ({placeholders})"


def _book_params(book_ids: Optional[List[str]]) -> dict:
    if not book_ids:
        return {}
    return {f"bk{i}": str(b) for i, b in enumerate(book_ids)}


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
        self,
        start: Optional[date] = None,
        end: Optional[date] = None,
        book_ids: Optional[List[str]] = None,
    ) -> dict:
        """Headline sales summary.

        When ``book_ids`` is supplied every figure is scoped to those books:
        revenue and items are summed from the matching order_items only, and an
        order counts once if it contains at least one of the books. This lets an
        author see the totals for just their own catalogue.
        """
        params = {
            **_status_params(),
            **_date_params(start, end),
            **_book_params(book_ids),
        }

        if book_ids:
            book_clause = _book_clause(book_ids)
            # Scope every aggregate to the requested books via order_items.
            totals_sql = text(
                f"""
                SELECT
                    COALESCE(SUM(oi.quantity * oi.unit_price), 0) AS total_revenue,
                    COUNT(DISTINCT o.id)                          AS total_orders
                FROM order_items oi
                JOIN orders o ON o.id = oi.order_id
                WHERE {_status_clause()} {_date_filter()} {book_clause}
                """
            )
            items_sql = text(
                f"""
                SELECT COALESCE(SUM(oi.quantity), 0) AS items_sold
                FROM order_items oi
                JOIN orders o ON o.id = oi.order_id
                WHERE {_status_clause()} {_date_filter()} {book_clause}
                """
            )
            month_sql = text(
                f"""
                SELECT COALESCE(SUM(oi.quantity * oi.unit_price), 0) AS monthly_revenue
                FROM order_items oi
                JOIN orders o ON o.id = oi.order_id
                WHERE {_status_clause()} {book_clause}
                  AND date_trunc('month', o.created_at) = date_trunc('month', now())
                """
            )
            month_params = {**_status_params(), **_book_params(book_ids)}
        else:
            totals_sql = text(
                f"""
                SELECT
                    COALESCE(SUM(o.total_amount), 0)       AS total_revenue,
                    COUNT(DISTINCT o.id)                   AS total_orders
                FROM orders o
                WHERE {_status_clause()} {_date_filter()}
                """
            )
            items_sql = text(
                f"""
                SELECT COALESCE(SUM(oi.quantity), 0) AS items_sold
                FROM order_items oi
                JOIN orders o ON o.id = oi.order_id
                WHERE {_status_clause()} {_date_filter()}
                """
            )
            month_sql = text(
                f"""
                SELECT COALESCE(SUM(o.total_amount), 0) AS monthly_revenue
                FROM orders o
                WHERE {_status_clause()}
                  AND date_trunc('month', o.created_at) = date_trunc('month', now())
                """
            )
            month_params = _status_params()

        totals = (await self.db.execute(totals_sql, params)).mappings().first()
        items = (await self.db.execute(items_sql, params)).mappings().first()
        month = (await self.db.execute(month_sql, month_params)).mappings().first()

        top = await self.top_selling_books(start, end, limit=5, book_ids=book_ids)

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
        self,
        start: Optional[date],
        end: Optional[date],
        limit: int = 10,
        book_ids: Optional[List[str]] = None,
    ) -> List[dict]:
        params = {
            **_status_params(),
            **_date_params(start, end),
            **_book_params(book_ids),
            "lim": limit,
        }
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
            WHERE {_status_clause()} {_date_filter()} {_book_clause(book_ids)}
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
        self,
        start: Optional[date] = None,
        end: Optional[date] = None,
        book_ids: Optional[List[str]] = None,
    ) -> List[dict]:
        params = {
            **_status_params(),
            **_date_params(start, end),
            **_book_params(book_ids),
        }
        # When scoped to books, derive both revenue and item counts from the
        # matching order_items so the series reflects only those books.
        if book_ids:
            sql = text(
                f"""
                SELECT
                    to_char(date_trunc('day', o.created_at), 'YYYY-MM-DD') AS period,
                    COALESCE(SUM(oi.quantity * oi.unit_price), 0)          AS revenue,
                    COUNT(DISTINCT o.id)                                   AS orders,
                    COALESCE(SUM(oi.quantity), 0)                          AS items_sold
                FROM order_items oi
                JOIN orders o ON o.id = oi.order_id
                WHERE {_status_clause()} {_date_filter()} {_book_clause(book_ids)}
                GROUP BY date_trunc('day', o.created_at)
                ORDER BY date_trunc('day', o.created_at)
                """
            )
            return self._timeseries(await self.db.execute(sql, params))
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
        self,
        start: Optional[date] = None,
        end: Optional[date] = None,
        book_ids: Optional[List[str]] = None,
    ) -> List[dict]:
        params = {
            **_status_params(),
            **_date_params(start, end),
            **_book_params(book_ids),
        }
        if book_ids:
            sql = text(
                f"""
                SELECT
                    to_char(date_trunc('month', o.created_at), 'YYYY-MM') AS period,
                    COALESCE(SUM(oi.quantity * oi.unit_price), 0)         AS revenue,
                    COUNT(DISTINCT o.id)                                  AS orders,
                    COALESCE(SUM(oi.quantity), 0)                         AS items_sold
                FROM order_items oi
                JOIN orders o ON o.id = oi.order_id
                WHERE {_status_clause()} {_date_filter()} {_book_clause(book_ids)}
                GROUP BY date_trunc('month', o.created_at)
                ORDER BY date_trunc('month', o.created_at)
                """
            )
            return self._timeseries(await self.db.execute(sql, params))
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

    async def book_performance(
        self,
        book_id: str,
        start: Optional[date] = None,
        end: Optional[date] = None,
    ) -> dict:
        """Per-book sales performance: headline totals plus a daily series.

        Powers the "analytics for this particular book" view on the author
        dashboard. Returns zeros (not an error) for a book with no sales so the
        UI can always render a card.
        """
        params = {
            **_status_params(),
            **_date_params(start, end),
            "bk0": str(book_id),
        }
        book_clause = "AND oi.book_id = :bk0"

        totals_sql = text(
            f"""
            SELECT
                COALESCE(SUM(oi.quantity), 0)                 AS units_sold,
                COALESCE(SUM(oi.quantity * oi.unit_price), 0) AS revenue,
                COUNT(DISTINCT o.id)                          AS orders
            FROM order_items oi
            JOIN orders o ON o.id = oi.order_id
            WHERE {_status_clause()} {_date_filter()} {book_clause}
            """
        )
        totals = (await self.db.execute(totals_sql, params)).mappings().first()

        meta_sql = text(
            "SELECT id::text AS book_id, title, author FROM books WHERE id = :bk0"
        )
        meta = (await self.db.execute(meta_sql, {"bk0": str(book_id)})).mappings().first()

        series = await self.daily(start, end, book_ids=[str(book_id)])

        units = int(totals["units_sold"])
        revenue = float(totals["revenue"])
        orders = int(totals["orders"])
        return {
            "book_id": str(book_id),
            "title": meta["title"] if meta else None,
            "author": meta["author"] if meta else None,
            "units_sold": units,
            "revenue": round(revenue, 2),
            "orders": orders,
            "average_units_per_order": round(units / orders, 2) if orders else 0.0,
            "daily": series,
        }


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
