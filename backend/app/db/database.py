from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from app.core.config import settings

# SQLite와 PostgreSQL에 따라 엔진 설정 분리
if settings.DATABASE_URL.startswith("sqlite"):
    # SQLite는 StaticPool 사용 (pool_size 지원 안함)
    from sqlalchemy.pool import StaticPool
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=settings.DEBUG,
        future=True,
        connect_args={
            "timeout": 30,
            "check_same_thread": False,
        },
        poolclass=StaticPool,
    )
else:
    # PostgreSQL 등은 connection pool 사용
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=settings.DEBUG,
        future=True,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
        pool_recycle=3600,
    )

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Create sync engine and session factory for background tasks
if settings.DATABASE_URL_SYNC.startswith("sqlite"):
    sync_engine = create_engine(
        settings.DATABASE_URL_SYNC,
        echo=settings.DEBUG,
        connect_args={"check_same_thread": False},
    )
else:
    sync_engine = create_engine(
        settings.DATABASE_URL_SYNC,
        echo=settings.DEBUG,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
    )

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=sync_engine
)

# Base class for models
Base = declarative_base()


async def get_db() -> AsyncSession:
    """Dependency for getting async database sessions"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
