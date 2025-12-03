from fastapi import FastAPI
from sqlalchemy import text

from db import engine

app = FastAPI(title="Tokka Intern Pokemon Service - Stage 2")


@app.get("/health")
async def health_check():
    """
    Health endpoint.

    Now it checks:
    - The app is running
    - The database is reachable (simple SELECT 1)
    """
    try:
        async with engine.connect() as conn:
            # 'text' safely wraps raw SQL
            await conn.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        # If anything goes wrong connecting to DB, record it
        db_status = f"error: {e!s}"

    return {
        "status": "ok",
        "db": db_status,
    }
