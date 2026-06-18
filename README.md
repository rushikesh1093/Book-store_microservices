# bookstore-microservices

FastAPI analytics and reporting microservice for the Enterprise Book Store platform.

## Tech Stack

- **FastAPI 0.111** — ASGI web framework
- **Pydantic v2** — data validation
- **SQLAlchemy 2** — ORM
- **Alembic** — database migrations
- **PostgreSQL** (AWS RDS) — production database
- **Railway** — hosting platform

## Local Setup

```bash
# 1. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Copy and configure environment file
cp .env.example .env
# Fill in DATABASE_URL and DJANGO_API_URL

# 4. Start the development server (http://localhost:8001)
uvicorn app.main:app --reload --port 8001
```

## API Docs

Once running, interactive docs are available at:
- Swagger UI: http://localhost:8001/docs
- ReDoc: http://localhost:8001/redoc

## Environment Variables

| Variable         | Description                                  |
|------------------|----------------------------------------------|
| `DATABASE_URL`   | PostgreSQL connection string (AWS RDS)        |
| `DJANGO_API_URL` | Base URL of the Django backend               |
| `CORS_ORIGINS`   | Comma-separated allowed CORS origins          |
| `APP_DEBUG`      | `True` for development, `False` for prod     |

## Running Tests

```bash
pytest app/tests/ -v
```

## Deployment Target

**Railway** — configuration in `railway.json`.
Health probe endpoint: `GET /health` → `{"status": "ok"}`

## Endpoint Overview

| Method | Path                              | Status         |
|--------|-----------------------------------|----------------|
| GET    | `/health`                         | ✅ Implemented |
| GET    | `/analytics/sales/summary`        | ✅ Implemented |
| GET    | `/analytics/sales/daily`          | ✅ Implemented |
| GET    | `/analytics/sales/monthly`        | ✅ Implemented |
| GET    | `/analytics/sales/top-books`      | ✅ Implemented |
| GET    | `/analytics/sales/by-author`      | ✅ Implemented |
| GET    | `/analytics/sales/by-category`    | ✅ Implemented |
| GET    | `/analytics/sales/book/{book_id}` | ✅ Implemented |
| GET    | `/analytics/inventory/health`     | ✅ Implemented |
| GET    | `/analytics/customers/ltv`        | ✅ Implemented |
| POST   | `/reports/generate`               | ✅ Implemented |
| GET    | `/reports/{sales,inventory,customers}` | ✅ Implemented |

### Scoping sales to specific books

The sales summary, daily, monthly and top-books endpoints accept an optional
`book_ids` query parameter (comma-separated UUIDs). When supplied, all figures
are scoped to those books only. The Django backend uses this to power
author-scoped dashboards (an author sees totals for just the books they own):

```
GET /analytics/sales/summary?book_ids=<uuid1>,<uuid2>
GET /analytics/sales/book/<uuid>      # single-book totals + daily series
```
