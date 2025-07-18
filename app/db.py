import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite+aiosqlite:///./authfilter.db"  # Default to local SQLite file
)

# Ensure DATABASE_URL is not None
if DATABASE_URL is None:
    DATABASE_URL = "sqlite+aiosqlite:///./authfilter.db"

# Convert sync URLs to async URLs for the application
if DATABASE_URL and DATABASE_URL.startswith("mysql+pymysql://"):
    DATABASE_URL = DATABASE_URL.replace("mysql+pymysql://", "mysql+aiomysql://")

# Defer engine creation to avoid import issues during migrations
_engine = None
_async_session = None

def get_engine():
    global _engine
    if _engine is None:
        _engine = create_async_engine(DATABASE_URL, echo=True, future=True)
    return _engine

def get_async_session_maker():
    global _async_session
    if _async_session is None:
        _async_session = async_sessionmaker(get_engine(), expire_on_commit=False, class_=AsyncSession)
    return _async_session

Base = declarative_base()

# Dependency for FastAPI
async def get_async_session() -> AsyncSession:
    async with get_async_session_maker()() as session:
        yield session
