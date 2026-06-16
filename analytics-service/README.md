# Enterprise Book Store — Analytics Microservice

A standalone **FastAPI** microservice providing sales, inventory and customer
analytics, report generation, Redis-driven event processing and scheduled ETL
jobs. It is **independent of the Django backend** and reads from the shared
PostgreSQL database (and shared Redis).

## Architecture

```
analytics-service/
├── app/
│   ├── main.py              # FastAPI app + lifespan (consumer + scheduler)
│   ├── config.py            # pydantic-settings configuration
│   ├── database.py          # async + sync SQLAlchemy engines
│   ├── redis_client.py      # shared async Redis client
│   ├── routers/             # HTTP endpoints
│   │   ├── health.py
│   │   ├── sales.py
│   │   ├── inventory.py
│   │   ├── customer.py
│   │   ├── reports.py
│   │   └── exports.py
│   ├── services/            # business logic / SQL
│   │   ├── sales_service.py
│   │   ├── inventory_service.py
│   │   ├── customer_service.py
│   │   ├── report_service.py
│   │   └── redis_consumer.py
│   ├── scheduler/jobs.py    # APScheduler ETL jobs
│   └── models/              # SQLAlchemy tables + Pydantic schemas
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```

## Endpoints

| Method | Path | Description |
| ------ | ---- | ----------- |
| GET  | `/health` | Service + PostgreSQL + Redis status |
| GET  | `/analytics/sales/summary` | Revenue, orders, AOV, top sellers |
| GET  | `/analytics/sales/daily` | Daily revenue time series |
| GET  | `/analytics/sales/monthly` | Monthly revenue time series |
| GET  | `/analytics/sales/by-category` | Revenue grouped by category |
| GET  | `/analytics/sales/by-author` | Revenue grouped by author |
| GET  | `/analytics/inventory/health` | Stock levels + inventory value |
| GET  | `/analytics/inventory/turnover` | Turnover ratios |
| GET  | `/analytics/inventory/slow-movers` | Stocked but non-selling titles |
| GET  | `/analytics/inventory/reorder-forecast` | Reorder recommendations |
| GET  | `/analytics/customers/cohorts` | Signup cohort retention |
| GET  | `/analytics/customers/ltv` | Lifetime value + repeat rate |
| GET  | `/analytics/customers/acquisition` | New customers per month |
| GET  | `/analytics/customers/churn-risk` | At-risk customers |
| POST | `/reports/generate` | Generate PDF/CSV/Excel report |
| GET  | `/reports/{id}` | Report job status |
| GET  | `/reports/{id}/download` | Download a generated report |
| GET  | `/exports/sales.csv` | Stream sales as CSV |
| GET  | `/exports/sales.xlsx` | Stream sales as Excel |

Interactive docs at **`/docs`** (Swagger) and **`/redoc`**.

## Running locally

```bash
cd bookstore-microservices/analytics-service
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt

copy .env.example .env          # then set DATABASE_URL and REDIS_URL
uvicorn app.main:app --reload --port 8001
```

## Running with Docker

```bash
cd bookstore-microservices/analytics-service
copy .env.example .env          # set DATABASE_URL (Neon) — REDIS_URL defaults to the compose Redis
docker compose up --build
```

The service listens on **port 8001**.

## Notes on the data model

- Revenue counts only orders whose status is in `SALE_STATUSES`
  (`confirmed, processing, shipped, delivered`) — configurable via env.
- `books.author` is a free-text field, so **by-author** groups on that string.
- The `books` table has no category foreign key in the current schema. The
  **by-category** endpoint uses an optional `book_categories(book_id, category_id)`
  association table if present, otherwise falls back to grouping by `language`.
- Effective stock is `COALESCE(inventory_items.quantity, books.stock)`.
- The service creates its own tables (`analytics_events`,
  `analytics_event_aggregates`, `analytics_report_jobs`) and does not modify
  Django-managed tables.

## Event processing

The Redis consumer subscribes to `order_created`, `book_viewed`,
`search_query`, and `recommendation_clicked`, persisting each event to
`analytics_events`. The monthly aggregation job rolls these into
`analytics_event_aggregates`.

## Scheduled jobs (APScheduler, UTC)

| Job | Schedule |
| --- | -------- |
| Daily sales refresh | 01:00 daily |
| Inventory refresh | 02:00 daily |
| Weekly customer analytics | Mondays 03:00 |
| Monthly aggregation | 1st of month 04:00 |
