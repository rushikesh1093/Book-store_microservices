"""
app/services/inventory_service.py

Inventory analytics. Uses the ``books`` table as the base and LEFT JOINs the
optional ``inventory_items`` table (richer stock data). Effective stock is
COALESCE(inventory_items.quantity, books.stock); reorder level falls back to a
sensible default when no inventory row exists.
"""
from datetime import date
from typing import List, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings

# Effective stock / reorder expressions reused across queries.
_STOCK = "COALESCE(i.quantity, b.stock, 0)"
_REORDER = "COALESCE(i.reorder_level, 10)"
_BASE_JOIN = "FROM books b LEFT JOIN inventory_items i ON i.book_id = b.id"


def _status_clause(prefix: str = "o") -> str:
    placeholders = ", ".join(f":st{i}" for i in range(len(settings.SALE_STATUSES)))
    return f"{prefix}.status IN ({placeholders})"


def _status_params() -> dict:
    return {f"st{i}": s for i, s in enumerate(settings.SALE_STATUSES)}


class InventoryService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def health(self) -> dict:
        totals_sql = text(
            f"""
            SELECT
                COUNT(*)                                            AS total_books,
                COUNT(*) FILTER (WHERE {_STOCK} > {_REORDER})        AS in_stock,
                COUNT(*) FILTER (WHERE {_STOCK} > 0
                                  AND {_STOCK} <= {_REORDER})        AS low_stock,
                COUNT(*) FILTER (WHERE {_STOCK} = 0)                 AS out_of_stock,
                COALESCE(SUM({_STOCK} * b.price), 0)                 AS inventory_value
            {_BASE_JOIN}
            WHERE b.is_active = TRUE
            """
        )
        totals = (await self.db.execute(totals_sql)).mappings().first()

        low_sql = text(
            f"""
            SELECT b.id::text AS book_id, b.title, {_STOCK} AS stock,
                   {_REORDER} AS reorder_level
            {_BASE_JOIN}
            WHERE b.is_active = TRUE AND {_STOCK} > 0 AND {_STOCK} <= {_REORDER}
            ORDER BY {_STOCK} ASC
            LIMIT 50
            """
        )
        low = (await self.db.execute(low_sql)).mappings().all()

        oos_sql = text(
            f"""
            SELECT b.id::text AS book_id, b.title
            {_BASE_JOIN}
            WHERE b.is_active = TRUE AND {_STOCK} = 0
            ORDER BY b.title
            LIMIT 50
            """
        )
        oos = (await self.db.execute(oos_sql)).mappings().all()

        return {
            "total_books": int(totals["total_books"]),
            "in_stock": int(totals["in_stock"]),
            "low_stock": int(totals["low_stock"]),
            "out_of_stock": int(totals["out_of_stock"]),
            "inventory_value": round(float(totals["inventory_value"]), 2),
            "low_stock_books": [
                {
                    "book_id": r["book_id"],
                    "title": r["title"],
                    "stock": int(r["stock"]),
                    "reorder_level": int(r["reorder_level"]),
                }
                for r in low
            ],
            "out_of_stock_books": [
                {"book_id": r["book_id"], "title": r["title"]} for r in oos
            ],
        }

    async def turnover(self, days: int = 90, limit: int = 50) -> List[dict]:
        """
        Inventory turnover = units sold in the window / current stock.
        Higher ratio => faster moving.
        """
        params = {**_status_params(), "days": days, "lim": limit}
        sql = text(
            f"""
            SELECT
                b.id::text                                  AS book_id,
                b.title                                     AS title,
                COALESCE(sales.units_sold, 0)               AS units_sold,
                {_STOCK}                                    AS current_stock,
                CASE WHEN {_STOCK} > 0
                     THEN ROUND(COALESCE(sales.units_sold, 0)::numeric / {_STOCK}, 3)
                     ELSE 0 END                             AS turnover_ratio
            {_BASE_JOIN}
            LEFT JOIN (
                SELECT oi.book_id, SUM(oi.quantity) AS units_sold
                FROM order_items oi
                JOIN orders o ON o.id = oi.order_id
                WHERE {_status_clause()}
                  AND o.created_at >= now() - (:days || ' days')::interval
                GROUP BY oi.book_id
            ) sales ON sales.book_id = b.id
            WHERE b.is_active = TRUE
            ORDER BY turnover_ratio DESC
            LIMIT :lim
            """
        )
        rows = (await self.db.execute(sql, params)).mappings().all()
        return [
            {
                "book_id": r["book_id"],
                "title": r["title"],
                "units_sold": int(r["units_sold"]),
                "current_stock": int(r["current_stock"]),
                "turnover_ratio": float(r["turnover_ratio"]),
            }
            for r in rows
        ]

    async def slow_movers(
        self, days: Optional[int] = None, limit: int = 50
    ) -> List[dict]:
        """Books with stock on hand but little/no sales in the window."""
        days = days or settings.SLOW_MOVER_DAYS
        params = {**_status_params(), "days": days, "lim": limit}
        sql = text(
            f"""
            SELECT
                b.id::text                       AS book_id,
                b.title                          AS title,
                {_STOCK}                         AS current_stock,
                COALESCE(sales.units_sold, 0)    AS units_sold,
                b.created_at                     AS listed_at
            {_BASE_JOIN}
            LEFT JOIN (
                SELECT oi.book_id, SUM(oi.quantity) AS units_sold
                FROM order_items oi
                JOIN orders o ON o.id = oi.order_id
                WHERE {_status_clause()}
                  AND o.created_at >= now() - (:days || ' days')::interval
                GROUP BY oi.book_id
            ) sales ON sales.book_id = b.id
            WHERE b.is_active = TRUE
              AND {_STOCK} > 0
              AND COALESCE(sales.units_sold, 0) = 0
            ORDER BY current_stock DESC
            LIMIT :lim
            """
        )
        rows = (await self.db.execute(sql, params)).mappings().all()
        return [
            {
                "book_id": r["book_id"],
                "title": r["title"],
                "current_stock": int(r["current_stock"]),
                "units_sold": int(r["units_sold"]),
                "days_window": days,
            }
            for r in rows
        ]

    async def reorder_forecast(self, days: int = 30, limit: int = 50) -> List[dict]:
        """
        Recommend reorder quantities based on recent sales velocity.

        avg_daily_sales = units sold in window / days
        recommended_reorder_qty targets ~30 days of cover above the reorder
        level, minus current stock.
        """
        params = {**_status_params(), "days": days, "lim": limit}
        sql = text(
            f"""
            SELECT
                b.id::text                                          AS book_id,
                b.title                                             AS title,
                {_STOCK}                                            AS current_stock,
                {_REORDER}                                          AS reorder_level,
                ROUND(COALESCE(sales.units_sold, 0)::numeric / :days, 3) AS avg_daily_sales
            {_BASE_JOIN}
            LEFT JOIN (
                SELECT oi.book_id, SUM(oi.quantity) AS units_sold
                FROM order_items oi
                JOIN orders o ON o.id = oi.order_id
                WHERE {_status_clause()}
                  AND o.created_at >= now() - (:days || ' days')::interval
                GROUP BY oi.book_id
            ) sales ON sales.book_id = b.id
            WHERE b.is_active = TRUE
              AND {_STOCK} <= {_REORDER}
            ORDER BY avg_daily_sales DESC
            LIMIT :lim
            """
        )
        rows = (await self.db.execute(sql, params)).mappings().all()
        out: List[dict] = []
        for r in rows:
            avg_daily = float(r["avg_daily_sales"])
            current = int(r["current_stock"])
            reorder_level = int(r["reorder_level"])
            # Target 30 days of cover above the reorder buffer.
            target = int(round(avg_daily * 30)) + reorder_level
            recommended = max(target - current, reorder_level)
            out.append(
                {
                    "book_id": r["book_id"],
                    "title": r["title"],
                    "current_stock": current,
                    "reorder_level": reorder_level,
                    "avg_daily_sales": avg_daily,
                    "recommended_reorder_qty": recommended,
                }
            )
        return out
