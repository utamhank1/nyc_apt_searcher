from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine, AsyncSession
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

db_url = settings.database_url

# Railway PostgreSQL URLs start with postgres:// but SQLAlchemy needs postgresql+asyncpg://
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql+asyncpg://", 1)
elif db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

engine = create_async_engine(db_url, echo=False)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with async_session_factory() as session:
        yield session


async def init_db():
    import app.models.listing  # noqa
    import app.models.search_config  # noqa
    import app.models.calendar_connection  # noqa
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Add columns that may be missing from existing tables
    async with engine.begin() as conn:
        for col, coltype, default in [
            ("is_favorite", "BOOLEAN", "FALSE"),
            ("search_config_id", "INTEGER", "NULL"),
            ("search_name", "VARCHAR(100)", "NULL"),
            ("available_date", "VARCHAR(20)", "NULL"),
        ]:
            try:
                await conn.execute(
                    __import__("sqlalchemy").text(
                        f"ALTER TABLE listings ADD COLUMN {col} {coltype} DEFAULT {default}"
                    )
                )
            except Exception:
                pass  # column already exists
