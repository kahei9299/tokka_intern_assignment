import os
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy import text

from models import Base  

# Connection string for the async DB engine
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@db:5432/tokka_intern_assignment",
)

# Global async engine
engine: AsyncEngine = create_async_engine(
    DATABASE_URL,
    echo=False,   # set to True to see all SQL in logs
    future=True,
)

# Session factory for getting AsyncSession objects
AsyncSessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that provides a database session (AsyncSession)
    to request handlers.

    Usage in endpoints:
        async def some_endpoint(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        yield session


async def run_migrations() -> None:
    """
    Simple, idempotent migration function.

    - Creates the 'pokemon' table if it does not exist.
    - Creates the 'pokemon_types' table if it does not exist.
    """
    async with engine.begin() as conn:
        # Main pokemon table
        await conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS pokemon (
                    pokemon_id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    base_experience INTEGER,
                    height INTEGER,
                    "order" INTEGER,
                    weight INTEGER,
                    location_area_encounters TEXT
                );
                """
            )
        )

        # Types table (normalized)
        await conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS pokemon_types (
                    pokemon_id INTEGER REFERENCES pokemon(pokemon_id) ON DELETE CASCADE,
                    type_name TEXT NOT NULL,
                    type_url TEXT NOT NULL,
                    PRIMARY KEY (pokemon_id, type_name)
                );
                """
            )
        )
        
        # add location_name column if it doesn't exist
        await conn.execute(
            text(
                """
                ALTER TABLE pokemon
                ADD COLUMN IF NOT EXISTS location_name TEXT;
                """
            )
        )
        
        # add nature column if it doesn't exist
        await conn.execute(
            text(
                """
                ALTER TABLE pokemon
                ADD COLUMN IF NOT EXISTS nature TEXT;
                """
            )
        )