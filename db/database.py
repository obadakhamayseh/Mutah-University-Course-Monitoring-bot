import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from config import DATABASE_URL
from .models import Base

logger = logging.getLogger(__name__)

engine_kwargs = {
    "echo": False,
    "future": True,
}

if "sqlite" in DATABASE_URL:
    engine_kwargs["connect_args"] = {"timeout": 30}
else:
    engine_kwargs["pool_pre_ping"] = True
    engine_kwargs["pool_recycle"] = 300
    engine_kwargs["pool_size"] = 10
    engine_kwargs["max_overflow"] = 20

engine = create_async_engine(
    DATABASE_URL,
    **engine_kwargs,
)

async_session = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db() -> None:
    """Creates tables if they don't exist, adds any missing columns, and optimizes SQLite settings."""
    async with engine.begin() as conn:
        if "sqlite" in DATABASE_URL:
            await conn.execute(text("PRAGMA journal_mode=WAL;"))
            await conn.execute(text("PRAGMA busy_timeout=30000;"))
        await conn.run_sync(Base.metadata.create_all)

        # Ensure sub_type column exists in subscriptions
        try:
            await conn.execute(text("ALTER TABLE subscriptions ADD COLUMN sub_type VARCHAR(20) DEFAULT 'SEAT';"))
        except Exception:
            pass

        # Ensure new detail columns exist in section_cache
        cache_cols = [
            ("instructor", "VARCHAR(100)"),
            ("days", "VARCHAR(50)"),
            ("time_from", "VARCHAR(20)"),
            ("time_to", "VARCHAR(20)"),
            ("room", "VARCHAR(50)"),
            ("notes", "VARCHAR(255)"),
        ]
        for col_name, col_type in cache_cols:
            try:
                await conn.execute(text(f"ALTER TABLE section_cache ADD COLUMN {col_name} {col_type};"))
            except Exception:
                pass

    logger.info("Database tables initialized and migrated successfully.")


async def get_db():
    """Dependency / context helper for database sessions."""
    async with async_session() as session:
        yield session
