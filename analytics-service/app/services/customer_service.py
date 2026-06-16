"""
app/services/customer_service.py

Customer analytics: lifetime value, cohorts, acquisition, churn risk.
Reads from ``users`` and ``orders``.
"""
from datetime import date
from typing import List, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings


def _status_clause(prefix: str = "o") -> str:
    placeholders = ", ".join(f":st{i}" for i in range(len(settings.SALE_STATUSES)))
    return f"{prefix}.status IN ({placeholders})"


def _status_params() -> dict:
    return {f"st{i}": s for i, s in enumerate(settings.SALE_STATUSES)}


class CustomerService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def ltv(self, limit: int = 10) -> dict:
        params = {**_status_params(), "lim": limit}

        agg_sql = text(
            f"""
            WITH per_customer AS (
                SELECT o.user_id,
                       SUM(o.total_amount) AS revenue,
                       COUNT(*)            AS order_count
                FROM orders o
                WHERE {_status_clause()}
                GROUP BY o.user_id
            )
            SELECT
                COUNT(*)                                          AS total_customers,
                COUNT(*) FILTER (WHERE order_count > 1)           AS repeat_customers,
                COALESCE(AVG(revenue), 0)                         AS avg_ltv,
                COALESCE(
                    percentile_cont(0.5) WITHIN GROUP (ORDER BY revenue), 0
                )                                                 AS median_ltv
            FROM per_customer
            """
        )
        agg = (await self.db.execute(agg_sql, _status_params())).mappings().first()

        top_sql = text(
            f"""
            SELECT
                u.id::text                          AS user_id,
                u.email                             AS email,
                ROUND(SUM(o.total_amount), 2)       AS lifetime_value,
                COUNT(*)                            AS orders
            FROM orders o
            JOIN users u ON u.id = o.user_id
            WHERE {_status_clause()}
            GROUP BY u.id, u.email
            ORDER BY lifetime_value DESC
            LIMIT :lim
            """
        )
        top = (await self.db.execute(top_sql, params)).mappings().all()

        total = int(agg["total_customers"])
        repeat = int(agg["repeat_customers"])
        return {
            "average_ltv": round(float(agg["avg_ltv"]), 2),
            "median_ltv": round(float(agg["median_ltv"]), 2),
            "repeat_customer_rate": round(repeat / total, 4) if total else 0.0,
            "total_customers": total,
            "repeat_customers": repeat,
            "top_customers": [
                {
                    "user_id": r["user_id"],
                    "email": r["email"],
                    "lifetime_value": float(r["lifetime_value"]),
                    "orders": int(r["orders"]),
                }
                for r in top
            ],
        }

    async def acquisition(
        self, start: Optional[date] = None, end: Optional[date] = None
    ) -> List[dict]:
        """New customers per month based on users.date_joined."""
        params = {"start": start, "end": end}
        sql = text(
            """
            SELECT
                to_char(date_trunc('month', u.date_joined), 'YYYY-MM') AS period,
                COUNT(*)                                               AS new_customers
            FROM users u
            WHERE (:start IS NULL OR u.date_joined >= :start)
              AND (:end IS NULL OR u.date_joined < (:end::date + INTERVAL '1 day'))
            GROUP BY date_trunc('month', u.date_joined)
            ORDER BY date_trunc('month', u.date_joined)
            """
        )
        rows = (await self.db.execute(sql, params)).mappings().all()
        return [
            {"period": r["period"], "new_customers": int(r["new_customers"])}
            for r in rows
        ]

    async def cohorts(self, months: int = 12) -> List[dict]:
        """
        Signup-month cohorts with monthly order-retention.

        For each cohort (month a user joined) we measure, for each subsequent
        month offset, how many of those users placed at least one qualifying
        order.
        """
        params = {**_status_params(), "months": months}
        sql = text(
            f"""
            WITH cohort AS (
                SELECT u.id AS user_id,
                       date_trunc('month', u.date_joined) AS cohort_month
                FROM users u
                WHERE u.date_joined >= date_trunc('month', now())
                                       - (:months || ' months')::interval
            ),
            activity AS (
                SELECT o.user_id,
                       date_trunc('month', o.created_at) AS active_month
                FROM orders o
                WHERE {_status_clause()}
                GROUP BY o.user_id, date_trunc('month', o.created_at)
            )
            SELECT
                to_char(c.cohort_month, 'YYYY-MM')                          AS cohort_month,
                (EXTRACT(YEAR FROM a.active_month) * 12 + EXTRACT(MONTH FROM a.active_month))
                - (EXTRACT(YEAR FROM c.cohort_month) * 12 + EXTRACT(MONTH FROM c.cohort_month))
                                                                            AS month_offset,
                COUNT(DISTINCT a.user_id)                                   AS active_customers
            FROM cohort c
            LEFT JOIN activity a
                   ON a.user_id = c.user_id
                  AND a.active_month >= c.cohort_month
            GROUP BY c.cohort_month, month_offset
            ORDER BY c.cohort_month, month_offset
            """
        )
        rows = (await self.db.execute(sql, params)).mappings().all()

        # Cohort sizes (total users per signup month).
        size_sql = text(
            """
            SELECT to_char(date_trunc('month', u.date_joined), 'YYYY-MM') AS cohort_month,
                   COUNT(*) AS customers
            FROM users u
            WHERE u.date_joined >= date_trunc('month', now())
                                   - (:months || ' months')::interval
            GROUP BY date_trunc('month', u.date_joined)
            """
        )
        sizes = {
            r["cohort_month"]: int(r["customers"])
            for r in (await self.db.execute(size_sql, {"months": months})).mappings()
        }

        cohorts: dict[str, dict] = {}
        for r in rows:
            cm = r["cohort_month"]
            entry = cohorts.setdefault(
                cm, {"cohort_month": cm, "customers": sizes.get(cm, 0), "retention": {}}
            )
            if r["month_offset"] is not None and r["active_customers"]:
                entry["retention"][str(int(r["month_offset"]))] = int(
                    r["active_customers"]
                )
        return list(cohorts.values())

    async def churn_risk(self, limit: int = 100) -> List[dict]:
        """
        Customers whose last qualifying order is older than CHURN_RISK_DAYS.
        Risk level scales with how long they've been silent.
        """
        params = {**_status_params(), "threshold": settings.CHURN_RISK_DAYS, "lim": limit}
        sql = text(
            f"""
            WITH last_order AS (
                SELECT o.user_id,
                       MAX(o.created_at) AS last_order_date,
                       SUM(o.total_amount) AS lifetime_value
                FROM orders o
                WHERE {_status_clause()}
                GROUP BY o.user_id
            )
            SELECT
                u.id::text                                          AS user_id,
                u.email                                             AS email,
                lo.last_order_date                                  AS last_order_date,
                EXTRACT(DAY FROM now() - lo.last_order_date)::int    AS days_since,
                ROUND(lo.lifetime_value, 2)                         AS lifetime_value
            FROM last_order lo
            JOIN users u ON u.id = lo.user_id
            WHERE lo.last_order_date < now() - (:threshold || ' days')::interval
            ORDER BY days_since DESC
            LIMIT :lim
            """
        )
        rows = (await self.db.execute(sql, params)).mappings().all()
        out: List[dict] = []
        for r in rows:
            days = int(r["days_since"]) if r["days_since"] is not None else None
            out.append(
                {
                    "user_id": r["user_id"],
                    "email": r["email"],
                    "last_order_date": (
                        r["last_order_date"].date() if r["last_order_date"] else None
                    ),
                    "days_since_last_order": days,
                    "lifetime_value": float(r["lifetime_value"]),
                    "risk_level": self._risk_level(days),
                }
            )
        return out

    @staticmethod
    def _risk_level(days: Optional[int]) -> str:
        if days is None:
            return "unknown"
        if days >= 180:
            return "high"
        if days >= 120:
            return "medium"
        return "low"
