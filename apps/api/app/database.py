"""
Database engine, session factory, and Base model for SQLAlchemy.
"""

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import event, text

from app.config import settings
from app.utils.logging import get_base_logger

logger = get_base_logger(__name__)


try:
    engine = create_async_engine(
        settings.DATABASE_URL,
        pool_size=settings.DATABASE_POOL_SIZE,
        max_overflow=settings.DATABASE_MAX_OVERFLOW,
        echo=settings.DEBUG,
        pool_pre_ping=True,
    )
    _engine_init_error = None
except Exception as e:
    logger.error("DATABASE ENGINE INITIALIZATION FAILED", exc_info=True)
    engine = None
    _engine_init_error = e

async_session_factory = (
    async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    if engine is not None
    else None
)

SessionLocal = async_session_factory


from app.models.base import Base


async def get_db():
    """FastAPI dependency: yields an async database session."""
    if async_session_factory is None:
        raise RuntimeError("Database engine is not initialized")

    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_tenant_db(firm_id: str):
    """
    FastAPI dependency: yields a session with RLS tenant context set.
    This ensures all queries are filtered to the given firm.
    """
    async with async_session_factory() as session:
        try:
            # Set the PostgreSQL session variable for RLS
            await session.execute(
                text("SET app.current_firm_id = :firm_id"),
                {"firm_id": firm_id},
            )
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
