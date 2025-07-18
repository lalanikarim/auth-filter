import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.main import app
from app.db import Base, get_async_session
from app.crud import is_user_allowed
import asyncio

# Use a separate in-memory SQLite DB for tests
test_db_url = "sqlite+aiosqlite:///:memory:"
engine_test = create_async_engine(test_db_url, echo=False, future=True)
TestingSessionLocal = async_sessionmaker(engine_test, expire_on_commit=False)

# Override the get_async_session dependency
def override_get_async_session():
    async def _override():
        async with TestingSessionLocal() as session:
            yield session
    return _override

app.dependency_overrides[get_async_session] = override_get_async_session()

@pytest.fixture(scope="session", autouse=True)
def setup_db():
    # Create tables
    async def init_models():
        async with engine_test.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    asyncio.get_event_loop().run_until_complete(init_models())
    yield
    # Drop tables after tests
    async def drop_models():
        async with engine_test.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
    asyncio.get_event_loop().run_until_complete(drop_models())

@pytest.mark.asyncio
async def test_web_assets_bypass_authorization():
    """Test that web asset files bypass authentication/authorization checks."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Test various web asset extensions
        web_asset_paths = [
            "/static/styles.css",
            "/js/app.js",
            "/images/logo.png",
            "/fonts/font.woff",
            "/favicon.ico",
            "/static/styles.css?v=1.0",
            "/js/app.js#main"
        ]
        
        for path in web_asset_paths:
            # Test that web assets are allowed without authentication
            # This should work because the web asset check happens before authentication
            resp = await ac.get(f"/api/authorize?url={path}")
            assert resp.status_code == 200, f"Web asset {path} should be accessible without authentication"
            data = resp.json()
            assert data["allowed"] == True, f"Web asset {path} should be allowed without authentication"

@pytest.mark.asyncio
async def test_non_web_assets_require_authorization():
    """Test that non-web asset files still require proper authorization."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Test various non-web asset paths
        non_web_asset_paths = [
            "/api/users",
            "/dashboard",
            "/profile",
            "/admin/settings",
            "/data.json",
            "/document.pdf"
        ]
        
        for path in non_web_asset_paths:
            # Test that non-web assets require authentication
            # This should fail with 401 because no authentication cookie is provided
            resp = await ac.get(f"/api/authorize?url={path}")
            assert resp.status_code == 401, f"Non-web asset {path} should require authentication" 