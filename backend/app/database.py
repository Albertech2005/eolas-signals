from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import settings
import redis.asyncio as redis
import structlog

logger = structlog.get_logger()


class Base(DeclarativeBase):
    pass


# Railway provides postgresql:// but asyncpg needs postgresql+asyncpg://
_db_url = settings.DATABASE_URL
if _db_url.startswith("postgresql://"):
    _db_url = _db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
elif _db_url.startswith("postgres://"):
    _db_url = _db_url.replace("postgres://", "postgresql+asyncpg://", 1)

engine = create_async_engine(
    _db_url,
    pool_size=settings.DATABASE_POOL_SIZE,  # default 5 — safe for Railway free tier
    max_overflow=2,   # reduced from 5 to stay within Railway Postgres connection limits
    pool_timeout=30,
    pool_recycle=1800,  # recycle connections every 30 min to avoid stale connections
    echo=settings.DEBUG,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Redis client
redis_client: redis.Redis = None


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Create all tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database initialized")


async def init_redis():
    """Initialize Redis connection pool."""
    global redis_client
    redis_client = redis.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
    )
    await redis_client.ping()
    logger.info("Redis connected")


async def get_redis() -> redis.Redis:
    return redis_client


async def close_connections():
    """Cleanup on shutdown."""
    await engine.dispose()
    if redis_client:
        await redis_client.aclose()
