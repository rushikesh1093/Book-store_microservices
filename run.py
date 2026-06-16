"""
run.py

Entrypoint. Ensures the correct asyncio event-loop policy on Windows (required
by psycopg's async driver) and starts uvicorn.

Environment:
    PORT          port to bind (default 8001; Render/Railway inject this)
    UVICORN_RELOAD set to "1"/"true" to enable autoreload (local dev only)

Usage:
    python run.py
"""
import asyncio
import os
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import uvicorn

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8001"))
    reload = os.getenv("UVICORN_RELOAD", "").lower() in ("1", "true", "yes")
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=reload)
