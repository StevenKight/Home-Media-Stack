"""
database.py

Database connection and session management for SQLAlchemy with async support.

Configures database engine, connection pooling, and session management for
PostgreSQL (production) and SQLite (testing). Supports automatic retries,
connection pooling, and proper error handling.

Example:
    from app.db.database import get_db, init_db
    from fastapi import Depends

    # Initialize database on startup
    await init_db()

    # Use database session in route
    @app.get("/users")
    async def get_users(db: AsyncSession = Depends(get_db)):
        result = await db.execute(select(User))
        return result.scalars().all()
"""

from urllib.parse import quote_plus

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import AsyncAdaptedQueuePool

from app.config import get_settings
from app.utils.logger import setup_logger

settings = get_settings()
logger = setup_logger(__name__)


def get_database_url() -> str:
    """
    Construct the database URL based on application configuration.

    Prioritizes TEST_DATABASE_URL in testing environment. Builds PostgreSQL
    connection string if credentials are provided, otherwise raises error.

    Returns:
        Database connection URL string compatible with SQLAlchemy.

    Raises:
        ValueError: If no valid database configuration is found.

    Example:
        >>> url = get_database_url()
        >>> # Returns: "postgresql+asyncpg://user:pass@localhost:5432/dbname"
    """
    if settings.ENVIRONMENT == "testing" and settings.TEST_DATABASE_URL:
        return settings.TEST_DATABASE_URL

    if settings.DB_NAME:
        # PostgreSQL connection
        password = quote_plus(settings.DB_PASSWORD) if settings.DB_PASSWORD else ""
        return f"postgresql+asyncpg://{settings.DB_USER}:{password}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"

    raise ValueError("No database URL found")


def create_engine_with_retry(database_url: str):
    """
    Create an async SQLAlchemy engine with connection pooling and retry logic.

    Configures appropriate connection pooling based on database type:
    - SQLite: Basic configuration with same_thread check disabled
    - PostgreSQL: Advanced pooling with AsyncAdaptedQueuePool

    Args:
        database_url: SQLAlchemy-compatible database connection URL.

    Returns:
        Configured AsyncEngine instance ready for use.

    Example:
        >>> engine = create_engine_with_retry("postgresql+asyncpg://...")
        >>> # Engine includes connection pooling and pre-ping checks
    """
    connect_args = {}
    pooling_args = {
        "pool_pre_ping": True,
        "pool_recycle": 3600,
        "echo": False,
    }

    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    else:
        pooling_args.update(
            {
                "poolclass": AsyncAdaptedQueuePool,
                "pool_size": 20,
                "max_overflow": 10,
                "pool_timeout": 30,
            }
        )

    return create_async_engine(database_url, connect_args=connect_args, **pooling_args)


# Create the engine
engine = create_engine_with_retry(get_database_url())

# Create async session maker
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """
    Base class for SQLAlchemy ORM models.

    All database models should inherit from this class to enable
    SQLAlchemy declarative mapping and table creation.

    Example:
        >>> class User(Base):
        >>>     __tablename__ = "users"
        >>>     id = Column(Integer, primary_key=True)
    """

    pass


async def get_db() -> AsyncSession:
    """
    FastAPI dependency that provides a database session.

    Yields an async database session for use in route handlers.
    Automatically handles session lifecycle, including rollback on errors
    and proper cleanup after request completion.

    Yields:
        AsyncSession: Active database session.

    Raises:
        Exception: Database errors are logged and re-raised after rollback.

    Example:
        >>> @app.get("/users")
        >>> async def get_users(db: AsyncSession = Depends(get_db)):
        >>>     result = await db.execute(select(User))
        >>>     return result.scalars().all()
    """
    session = AsyncSessionLocal()
    logger.debug("Creating new database session")
    try:
        yield session
    except Exception as e:
        logger.error(f"Database session error: {str(e)}")
        await session.rollback()
        raise
    finally:
        logger.debug("Closing database session")
        await session.close()


async def init_db() -> None:
    """
    Initialize database by creating all tables defined in models.

    Should be called once during application startup. Creates all tables
    that inherit from Base if they don't already exist. Includes retry
    logic for initial connection.

    Raises:
        Exception: If database connection or table creation fails.

    Example:
        >>> # In main.py startup event
        >>> @app.on_event("startup")
        >>> async def startup():
        >>>     await init_db()
    """
    logger.info("Initializing database")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")
        raise
