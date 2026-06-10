from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine, AsyncSession
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

engine = create_async_engine(settings.database_url, echo=False)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with async_session_factory() as session:
        yield session


async def init_db():
    import app.models.listing  # noqa: ensure models are registered
    import app.models.search_config  # noqa
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
