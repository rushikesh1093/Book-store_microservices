"""
app/scheduler/jobs.py

ETL / aggregation jobs run by APScheduler:

  * Daily sales refresh        -> recompute yesterday's sales totals.
  * Inventory refresh          -> snapshot low/out-of-stock counts.
  * Weekly customer analytics  -> refresh LTV / repeat snapshot.
  * Monthly aggregation        -> roll raw events into analytics_event_aggregates.

The jobs use the synchronous engine because APScheduler executors run them in
worker threads, outside the FastAPI event loop. Results are logged; the live
endpoints always compute fresh values directly from the database, so no Redis
cache is required (the service runs without Redis).
"""
import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import text

from app.config import settings
from app.database import sync_engine

logger = logging.getLogger("analytics.scheduler")

_scheduler: AsyncIOScheduler | None = None


def _status_in() -> str:
    return ", ".join(f"'{s}'" for s in settings.SALE_STATUSES)


# ── Job functions ──────────────────────────────────────────────
def daily_sales_refresh() -> None:
    logger.info("[job] daily_sales_refresh starting")
    sql = text(
        f"""
        SELECT
            COALESCE(SUM(total_amount), 0) AS revenue,
            COUNT(*)                       AS orders
        FROM orders
        WHERE status IN ({_status_in()})
          AND created_at >= (now()::date - INTERVAL '1 day')
          AND created_at <  now()::date
        """
    )
    with sync_engine.connect() as conn:
        row = conn.execute(sql).mappings().first()
    result = {
        "date": str(datetime.now(timezone.utc).date()),
        "revenue": float(row["revenue"]),
        "orders": int(row["orders"]),
        "refreshed_at": datetime.now(timezone.utc).isoformat(),
    }
    logger.info("[job] daily_sales_refresh done: %s", result)


def inventory_refresh() -> None:
    logger.info("[job] inventory_refresh starting")
    sql = text(
        """
        SELECT
            COUNT(*) FILTER (WHERE COALESCE(i.quantity, b.stock, 0) = 0)          AS out_of_stock,
            COUNT(*) FILTER (WHERE COALESCE(i.quantity, b.stock, 0) > 0
                              AND COALESCE(i.quantity, b.stock, 0)
                                  <= COALESCE(i.reorder_level, 10))               AS low_stock,
            COALESCE(SUM(COALESCE(i.quantity, b.stock, 0) * b.price), 0)          AS inventory_value
        FROM books b
        LEFT JOIN inventory_items i ON i.book_id = b.id
        WHERE b.is_active = TRUE
        """
    )
    with sync_engine.connect() as conn:
        row = conn.execute(sql).mappings().first()
    result = {
        "out_of_stock": int(row["out_of_stock"]),
        "low_stock": int(row["low_stock"]),
        "inventory_value": float(row["inventory_value"]),
        "refreshed_at": datetime.now(timezone.utc).isoformat(),
    }
    logger.info("[job] inventory_refresh done: %s", result)


def weekly_customer_analytics() -> None:
    logger.info("[job] weekly_customer_analytics starting")
    sql = text(
        f"""
        WITH per_customer AS (
            SELECT user_id, SUM(total_amount) AS revenue, COUNT(*) AS orders
            FROM orders
            WHERE status IN ({_status_in()})
            GROUP BY user_id
        )
        SELECT
            COUNT(*)                                AS total_customers,
            COUNT(*) FILTER (WHERE orders > 1)      AS repeat_customers,
            COALESCE(AVG(revenue), 0)               AS avg_ltv
        FROM per_customer
        """
    )
    with sync_engine.connect() as conn:
        row = conn.execute(sql).mappings().first()
    total = int(row["total_customers"])
    result = {
        "total_customers": total,
        "repeat_customers": int(row["repeat_customers"]),
        "repeat_rate": round(int(row["repeat_customers"]) / total, 4) if total else 0,
        "average_ltv": round(float(row["avg_ltv"]), 2),
        "refreshed_at": datetime.now(timezone.utc).isoformat(),
    }
    logger.info("[job] weekly_customer_analytics done: %s", result)


def monthly_aggregation() -> None:
    """Roll raw analytics_events into the daily aggregate table."""
    logger.info("[job] monthly_aggregation starting")
    sql = text(
        """
        INSERT INTO analytics_event_aggregates (id, bucket_date, event_type, count, created_at)
        SELECT
            gen_random_uuid()::text,
            to_char(created_at, 'YYYY-MM-DD'),
            event_type,
            COUNT(*),
            now()
        FROM analytics_events
        WHERE created_at >= date_trunc('month', now()) - INTERVAL '1 month'
        GROUP BY to_char(created_at, 'YYYY-MM-DD'), event_type
        """
    )
    try:
        with sync_engine.begin() as conn:
            conn.execute(sql)
        logger.info("[job] monthly_aggregation done")
    except Exception as exc:  # pragma: no cover - depends on pgcrypto for gen_random_uuid
        logger.warning("monthly_aggregation skipped: %s", exc)


# ── Scheduler lifecycle ────────────────────────────────────────
def start_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler and _scheduler.running:
        return _scheduler

    _scheduler = AsyncIOScheduler(timezone="UTC")
    _scheduler.add_job(
        daily_sales_refresh, CronTrigger(hour=1, minute=0),
        id="daily_sales_refresh", replace_existing=True,
    )
    _scheduler.add_job(
        inventory_refresh, CronTrigger(hour=2, minute=0),
        id="inventory_refresh", replace_existing=True,
    )
    _scheduler.add_job(
        weekly_customer_analytics, CronTrigger(day_of_week="mon", hour=3, minute=0),
        id="weekly_customer_analytics", replace_existing=True,
    )
    _scheduler.add_job(
        monthly_aggregation, CronTrigger(day=1, hour=4, minute=0),
        id="monthly_aggregation", replace_existing=True,
    )
    _scheduler.start()
    logger.info("APScheduler started with %d jobs.", len(_scheduler.get_jobs()))
    return _scheduler


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("APScheduler shut down.")
    _scheduler = None
