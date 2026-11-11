
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker
)
from sqlalchemy import inspect

from .models import Base
from settings import DB_URL


async_engine = create_async_engine(
    DB_URL,
    echo=False,
    pool_pre_ping=True
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    expire_on_commit=False,
    class_=AsyncSession
)


def migrate_database(connection):
    inspector = inspect(connection)

    if "users" not in inspector.get_table_names():
        return

    user_columns = {
        column["name"]
        for column in inspector.get_columns("users")
    }

    if "has_started" not in user_columns:
        connection.exec_driver_sql(
            """
            ALTER TABLE users
            ADD COLUMN has_started BOOLEAN NOT NULL DEFAULT FALSE
            """
        )


async def create_db_and_tables():
    async with async_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        await connection.run_sync(migrate_database)


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


async def close_database():
    await async_engine.dispose()
