import pytest
from app.crud import is_web_asset


def test_is_web_asset_with_allowed_extensions():
    """Test that web asset file extensions are correctly identified."""
    # Test common web asset extensions
    assert is_web_asset("/static/styles.css") == True
    assert is_web_asset("/js/app.js") == True
    assert is_web_asset("/images/logo.png") == True
    assert is_web_asset("/images/photo.jpg") == True
    assert is_web_asset("/images/photo.jpeg") == True
    assert is_web_asset("/icons/icon.svg") == True
    assert is_web_asset("/favicon.ico") == True
    assert is_web_asset("/fonts/font.woff") == True
    assert is_web_asset("/fonts/font.woff2") == True
    assert is_web_asset("/fonts/font.ttf") == True
    assert is_web_asset("/fonts/font.eot") == True
    assert is_web_asset("/app.js.map") == True


def test_is_web_asset_with_non_allowed_extensions():
    """Test that non-web asset file extensions are correctly identified."""
    # Test non-web asset extensions
    assert is_web_asset("/api/users") == False
    assert is_web_asset("/dashboard") == False
    assert is_web_asset("/profile.html") == False
    assert is_web_asset("/document.pdf") == False
    assert is_web_asset("/data.json") == False
    assert is_web_asset("/config.xml") == False
    assert is_web_asset("/script.py") == False


def test_is_web_asset_with_edge_cases():
    """Test edge cases for web asset detection."""
    # Test edge cases
    assert is_web_asset("") == False
    assert is_web_asset("/path/without/extension") == False
    assert is_web_asset("/path.with.multiple.dots.txt") == False  # Should check last extension
    assert is_web_asset("/path/with.extension.CSS") == True  # Case insensitive
    assert is_web_asset("/path/with.extension.JS") == True  # Case insensitive


def test_is_web_asset_with_query_parameters():
    """Test that web asset detection works with query parameters."""
    assert is_web_asset("/static/styles.css?v=1.0") == True
    assert is_web_asset("/js/app.js?cache=bust") == True
    assert is_web_asset("/images/logo.png?size=large") == True


def test_is_web_asset_with_fragments():
    """Test that web asset detection works with URL fragments."""
    assert is_web_asset("/static/styles.css#section") == True
    assert is_web_asset("/js/app.js#main") == True 