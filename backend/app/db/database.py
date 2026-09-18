from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from app.core.config import settings

# SQLite와 PostgreSQL에 따라 엔진 설정 분리
if settings.DATABASE_URL.startswith("sqlite"):
    # 예전엔 StaticPool(연결 1개)을 썼는데, 앱 안에서 도는 작업 워커와 HTTP 요청이
    # 같은 연결을 놓고 서로 기다리며 멈췄다(캠페인 키워드 확장 중 폴링 요청이 걸리면 영구 대기).
    # 세션마다 연결을 갖는 기본 풀 + WAL 모드로 바꿔 읽기/쓰기가 섞여도 진행되게 한다.
    from sqlalchemy import event
    from sqlalchemy.pool import AsyncAdaptedQueuePool

    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=settings.SQL_ECHO,
        future=True,
        connect_args={
            "timeout": 30,
            "check_same_thread": False,
        },
        poolclass=AsyncAdaptedQueuePool,
        pool_size=5,
        max_overflow=10,
    )

    @event.listens_for(engine.sync_engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _record):  # noqa: ANN001
        try:
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA synchronous=NORMAL")
            cur.execute("PRAGMA busy_timeout=30000")
            cur.close()
        except Exception:  # noqa: BLE001
            pass
else:
    # PostgreSQL 등은 connection pool 사용
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=settings.SQL_ECHO,
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
        echo=settings.SQL_ECHO,
        connect_args={"check_same_thread": False},
    )
else:
    sync_engine = create_engine(
        settings.DATABASE_URL_SYNC,
        echo=settings.SQL_ECHO,
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
