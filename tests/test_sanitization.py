import pytest
from app.utils import (
    sanitize_email, sanitize_url, sanitize_database_url, 
    sanitize_token, sanitize_environment_variables, sanitize_log_message
)


def test_sanitize_email():
    """Test email sanitization."""
    assert sanitize_email("user@example.com") == "u**r@example.com"
    assert sanitize_email("admin@test.org") == "a***n@test.org"
    assert sanitize_email("a@b.com") == "*@b.com"
    assert sanitize_email("") == ""
    assert sanitize_email("notanemail") == "notanemail"


def test_sanitize_url():
    """Test URL sanitization."""
    # Test with sensitive query parameters
    url = "https://example.com/auth?code=abc123&state=xyz&token=secret"
    sanitized = sanitize_url(url)
    assert "code=%2A%2A%2A" in sanitized  # URL encoded ***
    assert "state=%2A%2A%2A" in sanitized  # URL encoded ***
    assert "token=%2A%2A%2A" in sanitized  # URL encoded ***
    assert "abc123" not in sanitized
    assert "xyz" not in sanitized
    assert "secret" not in sanitized
    
    # Test with credentials in URL
    url_with_auth = "https://user:password@example.com/api"
    sanitized = sanitize_url(url_with_auth)
    assert "user:***" in sanitized
    assert "password" not in sanitized


def test_sanitize_database_url():
    """Test database URL sanitization."""
    db_url = "mysql+pymysql://user:secretpass@localhost:3306/mydb"
    sanitized = sanitize_database_url(db_url)
    assert "user:***" in sanitized
    assert "secretpass" not in sanitized
    assert "localhost:3306/mydb" in sanitized


def test_sanitize_token():
    """Test token sanitization."""
    token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
    sanitized = sanitize_token(token)
    assert sanitized == "eyJh...sw5c"
    
    short_token = "abc123"
    assert sanitize_token(short_token) == "***"


def test_sanitize_environment_variables():
    """Test environment variables sanitization."""
    env_vars = {
        "DATABASE_URL": "mysql://user:pass@localhost/db",
        "DB_PASSWORD": "secret123",
        "OAUTH2_CLIENT_SECRET": "client_secret_here",
        "NORMAL_VAR": "normal_value",
        "API_KEY": "key123"
    }
    
    sanitized = sanitize_environment_variables(env_vars)
    
    assert "user:***" in sanitized["DATABASE_URL"]
    assert "pass" not in sanitized["DATABASE_URL"]
    assert sanitized["DB_PASSWORD"] == "***"
    assert sanitized["OAUTH2_CLIENT_SECRET"] == "***"
    assert sanitized["API_KEY"] == "***"
    assert sanitized["NORMAL_VAR"] == "normal_value"


def test_sanitize_log_message():
    """Test log message sanitization."""
    message = "User john@example.com accessed /api with token eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
    sanitized = sanitize_log_message(message)
    
    assert "j**n@example.com" in sanitized
    assert "john@example.com" not in sanitized
    assert "eyJh...sw5c" in sanitized
    assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c" not in sanitized


def test_sanitize_log_message_with_database_url():
    """Test log message sanitization with database URLs."""
    message = "Connecting to mysql://user:password@localhost:3306/mydb"
    sanitized = sanitize_log_message(message)
    
    assert "user:***" in sanitized
    assert "password" not in sanitized 