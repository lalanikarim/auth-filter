import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_web_assets_no_auth_required():
    """Test that web assets can be accessed without authentication."""
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
            # These should all work without any authentication
            resp = await ac.get(f"/api/authorize?url={path}")
            assert resp.status_code == 200, f"Web asset {path} should be accessible without authentication"
            data = resp.json()
            assert data["allowed"] == True, f"Web asset {path} should be allowed"


@pytest.mark.asyncio
async def test_non_web_assets_auth_required():
    """Test that non-web assets require authentication."""
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
            # These should all fail with 401 because no authentication is provided
            resp = await ac.get(f"/api/authorize?url={path}")
            assert resp.status_code == 401, f"Non-web asset {path} should require authentication"
            assert "Not authenticated" in resp.json()["detail"], f"Non-web asset {path} should have authentication error"


@pytest.mark.asyncio
async def test_web_assets_with_auth_still_allowed():
    """Test that web assets are still allowed even when authentication is provided."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Test with authentication cookie (even though it's not needed for web assets)
        cookies = {"x-auth-email": "test@example.com"}
        
        web_asset_paths = [
            "/static/styles.css",
            "/js/app.js",
            "/images/logo.png"
        ]
        
        for path in web_asset_paths:
            # These should still work even with authentication provided
            resp = await ac.get(f"/api/authorize?url={path}", cookies=cookies)
            assert resp.status_code == 200, f"Web asset {path} should be accessible with authentication"
            data = resp.json()
            assert data["allowed"] == True, f"Web asset {path} should be allowed with authentication" 