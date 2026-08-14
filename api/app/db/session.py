from fastapi import Request
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from api.app.core.config import Settings, get_settings


def create_engine(settings: Settings | None = None) -> AsyncEngine:
    return create_async_engine((settings or get_settings()).database_url, pool_pre_ping=True)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def get_db_session(request: Request) -> AsyncSession:  # type: ignore[misc]
    factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with factory() as session:
        yield session
