"""
run.py

Local entrypoint. Ensures the correct asyncio event-loop policy on Windows
(required by psycopg's async driver) and starts uvicorn.

Usage:
    python run.py
"""
import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
    )
