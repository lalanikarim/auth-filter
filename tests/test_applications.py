import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.db import Base, get_async_session
from app import models  # Import models to ensure they are registered
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

# Use a separate in-memory SQLite DB for tests
test_db_url = "sqlite+aiosqlite:///applications_test.db"
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
    import asyncio
    asyncio.get_event_loop().run_until_complete(init_models())
    yield
    # Drop tables after tests
    async def drop_models():
        async with engine_test.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
    asyncio.get_event_loop().run_until_complete(drop_models())

@pytest.mark.asyncio
async def test_create_application():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/api/applications", json={
            "name": "Test App",
            "host": "test.example.com",
            "description": "A test application"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Test App"
        assert data["host"] == "test.example.com"
        assert data["description"] == "A test application"
        assert "app_id" in data
        assert "created_at" in data

@pytest.mark.asyncio
async def test_create_application_duplicate_name():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Create first application
        response1 = await ac.post("/api/applications", json={
            "name": "Duplicate App",
            "host": "app1.example.com",
            "description": "First app"
        })
        assert response1.status_code == 200
        
        # Try to create second application with same name
        response2 = await ac.post("/api/applications", json={
            "name": "Duplicate App",
            "host": "app2.example.com",
            "description": "Second app"
        })
        assert response2.status_code == 400
        assert "already exists" in response2.json()["detail"]

@pytest.mark.asyncio
async def test_create_application_duplicate_host():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Create first application
        response1 = await ac.post("/api/applications", json={
            "name": "App 1",
            "host": "duplicate.example.com",
            "description": "First app"
        })
        assert response1.status_code == 200
        
        # Try to create second application with same host
        response2 = await ac.post("/api/applications", json={
            "name": "App 2",
            "host": "duplicate.example.com",
            "description": "Second app"
        })
        assert response2.status_code == 400
        assert "already exists" in response2.json()["detail"]

@pytest.mark.asyncio
async def test_list_applications():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Create a test application
        await ac.post("/api/applications", json={
            "name": "List Test App",
            "host": "list.example.com",
            "description": "App for listing test"
        })
        
        response = await ac.get("/api/applications")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        
        # Find our test app
        test_app = next((app for app in data if app["name"] == "List Test App"), None)
        assert test_app is not None
        assert test_app["host"] == "list.example.com"

@pytest.mark.asyncio
async def test_get_application():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Create a test application
        create_response = await ac.post("/api/applications", json={
            "name": "Get Test App",
            "host": "get.example.com",
            "description": "App for get test"
        })
        app_id = create_response.json()["app_id"]
        
        # Get the application
        response = await ac.get(f"/api/applications/{app_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Get Test App"
        assert data["host"] == "get.example.com"
        assert data["app_id"] == app_id

@pytest.mark.asyncio
async def test_update_application():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Create a test application
        create_response = await ac.post("/api/applications", json={
            "name": "Update Test App",
            "host": "update.example.com",
            "description": "Original description"
        })
        app_id = create_response.json()["app_id"]
        
        # Update the application
        response = await ac.put(f"/api/applications/{app_id}", json={
            "name": "Updated Test App",
            "host": "updated.example.com",
            "description": "Updated description"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Test App"
        assert data["host"] == "updated.example.com"
        assert data["description"] == "Updated description"

@pytest.mark.asyncio
async def test_delete_application():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Create a test application
        create_response = await ac.post("/api/applications", json={
            "name": "Delete Test App",
            "host": "delete.example.com",
            "description": "App to be deleted"
        })
        app_id = create_response.json()["app_id"]
        
        # Delete the application
        response = await ac.delete(f"/api/applications/{app_id}")
        assert response.status_code == 200
        assert response.json()["message"] == "Application deleted successfully"
        
        # Verify it's deleted
        get_response = await ac.get(f"/api/applications/{app_id}")
        assert get_response.status_code == 404

@pytest.mark.asyncio
async def test_url_group_name_uniqueness_per_application():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Create an application
        app_response = await ac.post("/api/applications", json={
            "name": "URL Group Test App",
            "host": "urlgroup.example.com",
            "description": "App for URL group testing"
        })
        app_id = app_response.json()["app_id"]
        
        # Create first URL group
        response1 = await ac.post("/api/url-groups", json={
            "name": "Test Group",
            "app_id": app_id
        })
        assert response1.status_code == 200
        
        # Try to create second URL group with same name in same app
        response2 = await ac.post("/api/url-groups", json={
            "name": "Test Group",
            "app_id": app_id
        })
        assert response2.status_code == 400
        assert "already exists" in response2.json()["detail"]
        
        # Create URL group with same name in different app (should work)
        app_response2 = await ac.post("/api/applications", json={
            "name": "URL Group Test App 2",
            "host": "urlgroup2.example.com",
            "description": "Second app for URL group testing"
        })
        app_id2 = app_response2.json()["app_id"]
        
        response3 = await ac.post("/api/url-groups", json={
            "name": "Test Group",
            "app_id": app_id2
        })
        assert response3.status_code == 200 

@pytest.mark.asyncio
async def test_full_url_authorization():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Create an application
        app_response = await ac.post("/api/applications", json={
            "name": "Auth Test App",
            "host": "auth.example.com",
            "description": "App for authorization testing"
        })
        app_id = app_response.json()["app_id"]
        
        # Create user group
        user_group_response = await ac.post("/api/user-groups", json={"name": "Auth Users"})
        user_group_id = user_group_response.json()["group_id"]
        
        # Add user to group
        await ac.post(f"/api/user-groups/{user_group_id}/users", json={"email": "auth@example.com"})
        
        # Create URL group for the application
        url_group_response = await ac.post("/api/url-groups", json={
            "name": "Auth URLs",
            "app_id": app_id
        })
        url_group_id = url_group_response.json()["group_id"]
        
        # Add URL to group
        await ac.post(f"/api/url-groups/{url_group_id}/urls", json={"path": "/secret"})
        
        # Link user group to URL group
        await ac.post("/api/associations", json={
            "user_group_id": user_group_id,
            "url_group_id": url_group_id
        })
        
        # Test authorization with full URL (with user email cookie)
        response = await ac.get(
            "/api/authorize", 
            params={"url": "https://auth.example.com/secret"},
            cookies={"x-auth-email": "auth@example.com"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["allowed"] == True
        
        # Test authorization with different host (should be denied)
        response2 = await ac.get(
            "/api/authorize", 
            params={"url": "https://other.example.com/secret"},
            cookies={"x-auth-email": "auth@example.com"}
        )
        assert response2.status_code == 403
        data2 = response2.json()
        assert data2["allowed"] == False
        
        # Test authorization with relative path (should fall back to path-based auth)
        response3 = await ac.get(
            "/api/authorize", 
            params={"url": "/nonexistent"},
            cookies={"x-auth-email": "auth@example.com"}
        )
        assert response3.status_code == 403  # No matching permissions for relative path
        data3 = response3.json()
        assert data3["allowed"] == False 