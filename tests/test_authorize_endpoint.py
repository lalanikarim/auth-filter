import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_authorize_page_accessible_without_auth():
    """Test that the /authorize page is accessible without authentication."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Test GET /authorize without authentication
        resp = await ac.get("/authorize")
        assert resp.status_code == 200, "GET /authorize should be accessible without authentication"
        
        # Should return HTML content
        assert "text/html" in resp.headers.get("content-type", "")
        assert "Authorization Check" in resp.text


@pytest.mark.asyncio
async def test_authorize_post_accessible_without_auth():
    """Test that the POST /authorize endpoint is accessible without authentication."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Test POST /authorize without authentication using a web asset path
        # This will bypass database queries and work without tables
        form_data = {
            "email": "test@example.com",
            "url_path": "/static/styles.css"
        }
        resp = await ac.post("/authorize", data=form_data)
        assert resp.status_code == 200, "POST /authorize should be accessible without authentication"
        
        # Should return HTML content
        assert "text/html" in resp.headers.get("content-type", "")
        assert "Authorization Check" in resp.text


@pytest.mark.asyncio
async def test_authorize_with_query_parameters():
    """Test that /authorize works with query parameters."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Test with query parameters
        resp = await ac.get("/authorize?email=test@example.com&url_path=/dashboard")
        assert resp.status_code == 200, "GET /authorize with query params should be accessible"
        
        # Should return HTML content
        assert "text/html" in resp.headers.get("content-type", "")
        assert "Authorization Check" in resp.text 