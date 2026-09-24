import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from config import DATABASE_URL
from .models import Base

logger = logging.getLogger(__name__)

connect_args = {"timeout": 30} if "sqlite" in DATABASE_URL else {}

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    future=True,
    connect_args=connect_args,
)

async_session = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db() -> None:
    """Creates tables if they don't exist and optimizes SQLite settings."""
    async with engine.begin() as conn:
        if "sqlite" in DATABASE_URL:
            await conn.execute(text("PRAGMA journal_mode=WAL;"))
            await conn.execute(text("PRAGMA busy_timeout=30000;"))
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables initialized successfully (WAL mode enabled).")


async def get_db():
    """Dependency / context helper for database sessions."""
    async with async_session() as session:
        yield session
