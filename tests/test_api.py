import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.main import app
from app.db import Base, get_async_session
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
async def test_auth_valid():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/auth", json={"token": "user@example.com"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is True
        assert data["email"] == "user@example.com"

@pytest.mark.asyncio
async def test_auth_invalid():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/auth", json={"token": "notanemail"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is False

@pytest.mark.asyncio
async def test_create_user_group():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/user-groups", json={"name": "Admins"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Admins"
        assert "group_id" in data

@pytest.mark.asyncio
async def test_add_user_to_group():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Create group
        resp = await ac.post("/api/user-groups", json={"name": "Testers"})
        group_id = resp.json()["group_id"]
        # Add user
        resp2 = await ac.post(f"/api/user-groups/{group_id}/users", json={"email": "testuser@example.com"})
        assert resp2.status_code == 200
        assert resp2.json()["success"] is True

@pytest.mark.asyncio
async def test_add_user_to_nonexistent_group():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/user-groups/9999/users", json={"email": "nouser@example.com"})
        assert resp.status_code == 404

@pytest.mark.asyncio
async def test_create_url_group():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/url-groups", json={"name": "Protected"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Protected"
        assert "group_id" in data

@pytest.mark.asyncio
async def test_add_url_to_group():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Create group
        resp = await ac.post("/api/url-groups", json={"name": "Public"})
        group_id = resp.json()["group_id"]
        # Add URL
        resp2 = await ac.post(f"/api/url-groups/{group_id}/urls", json={"path": "/dashboard"})
        assert resp2.status_code == 200
        assert resp2.json()["success"] is True

@pytest.mark.asyncio
async def test_add_url_to_nonexistent_group():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/url-groups/9999/urls", json={"path": "/notfound"})
        assert resp.status_code == 404

@pytest.mark.asyncio
async def test_link_user_group_to_url_group():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Create user group
        resp1 = await ac.post("/api/user-groups", json={"name": "Linkers"})
        user_group_id = resp1.json()["group_id"]
        # Create url group
        resp2 = await ac.post("/api/url-groups", json={"name": "LinkURLs"})
        url_group_id = resp2.json()["group_id"]
        # Link them
        resp3 = await ac.post("/api/associations", json={"user_group_id": user_group_id, "url_group_id": url_group_id})
        assert resp3.status_code == 200
        assert resp3.json()["success"] is True

@pytest.mark.asyncio
async def test_link_user_group_to_nonexistent_url_group():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Create user group
        resp1 = await ac.post("/api/user-groups", json={"name": "NoURLGroup"})
        user_group_id = resp1.json()["group_id"]
        # Try to link to non-existent url group
        resp2 = await ac.post("/api/associations", json={"user_group_id": user_group_id, "url_group_id": 9999})
        assert resp2.status_code == 404

@pytest.mark.asyncio
async def test_link_nonexistent_user_group_to_url_group():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Create url group
        resp1 = await ac.post("/api/url-groups", json={"name": "NoUserGroup"})
        url_group_id = resp1.json()["group_id"]
        # Try to link non-existent user group
        resp2 = await ac.post("/api/associations", json={"user_group_id": 9999, "url_group_id": url_group_id})
        assert resp2.status_code == 404

@pytest.mark.asyncio
async def test_authorize_allowed():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Setup: create user, user group, url group, url, and link
        resp1 = await ac.post("/api/user-groups", json={"name": "AuthzGroup"})
        user_group_id = resp1.json()["group_id"]
        resp2 = await ac.post(f"/api/user-groups/{user_group_id}/users", json={"email": "authz@example.com"})
        resp3 = await ac.post("/api/url-groups", json={"name": "AuthzURLs"})
        url_group_id = resp3.json()["group_id"]
        resp4 = await ac.post(f"/api/url-groups/{url_group_id}/urls", json={"path": "/secret"})
        resp5 = await ac.post("/api/associations", json={"user_group_id": user_group_id, "url_group_id": url_group_id})
        # Should be allowed
        resp6 = await ac.post("/api/authorize", json={"email": "authz@example.com", "url_path": "/secret"})
        assert resp6.status_code == 200
        assert resp6.json()["allowed"] is True

@pytest.mark.asyncio
async def test_authorize_not_allowed():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Setup: create user, url group, url, but no association
        resp1 = await ac.post("/api/user-groups", json={"name": "NoAuthzGroup"})
        user_group_id = resp1.json()["group_id"]
        resp2 = await ac.post(f"/api/user-groups/{user_group_id}/users", json={"email": "noauthz@example.com"})
        resp3 = await ac.post("/api/url-groups", json={"name": "NoAuthzURLs"})
        url_group_id = resp3.json()["group_id"]
        resp4 = await ac.post(f"/api/url-groups/{url_group_id}/urls", json={"path": "/forbidden"})
        # Should not be allowed (no association)
        resp5 = await ac.post("/api/authorize", json={"email": "noauthz@example.com", "url_path": "/forbidden"})
        assert resp5.status_code == 200
        assert resp5.json()["allowed"] is False
