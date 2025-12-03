import os

from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine

# Read DATABASE_URL from environment variable, with a sensible default for Docker
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@db:5432/tokka_intern_assignment",
)

# Create a global async engine that can be imported elsewhere
engine: AsyncEngine = create_async_engine(
    DATABASE_URL,
    echo=False,      # set to True if you want to see SQL logs in the console
    future=True,
)
