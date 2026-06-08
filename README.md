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

| Method | Path                       | Status          |
|--------|----------------------------|-----------------|
| GET    | `/health`                  | ✅ Implemented  |
| GET    | `/analytics/sales`         | 501 Placeholder |
| GET    | `/analytics/sales/top-books` | 501 Placeholder |
| GET    | `/analytics/traffic`       | 501 Placeholder |
| GET    | `/analytics/customers`     | 501 Placeholder |
| GET    | `/reports/inventory`       | 501 Placeholder |
| GET    | `/reports/sales`           | 501 Placeholder |
| GET    | `/reports/customers`       | 501 Placeholder |

## Phase 0 Status

Health endpoint is functional.
All analytics and report endpoints return `501 Not Implemented`.
