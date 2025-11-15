from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from .config import settings


class Base(DeclarativeBase):
    """Declarative base all ORM models inherit from."""


engine = create_async_engine(settings.database_url, echo=False, future=True, pool_pre_ping=True)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


async def init_db() -> None:
    """Create database tables if they do not exist."""

    from . import models  # noqa: F401 - ensure models are imported

    async with engine.begin() as conn:
        await conn.run_sync(models.Base.metadata.create_all)


async def close_db() -> None:
    await engine.dispose()