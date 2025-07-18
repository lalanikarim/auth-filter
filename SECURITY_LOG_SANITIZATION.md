# Security Log Sanitization

This document outlines the security improvements made to remove sensitive information from logs in the AuthFilter application.

## Overview

The codebase has been updated to automatically sanitize sensitive information in all log messages, preventing the exposure of:
- Email addresses
- Passwords and secrets
- Database credentials
- OAuth2 tokens and codes
- JWT tokens
- Sensitive query parameters

## Changes Made

### 1. Created Sanitization Utility Module (`app/utils.py`)

A comprehensive utility module was created with the following functions:

- `sanitize_email()` - Masks email addresses (e.g., "user@example.com" → "u**r@example.com")
- `sanitize_url()` - Masks sensitive query parameters and credentials in URLs
- `sanitize_database_url()` - Masks database credentials in connection strings
- `sanitize_token()` - Masks JWT tokens (e.g., "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." → "eyJh...sw5c")
- `sanitize_environment_variables()` - Masks sensitive environment variables
- `sanitize_log_message()` - Automatically sanitizes common sensitive patterns in log messages
- `SanitizedLogger` - A logger wrapper that automatically sanitizes all log messages

### 2. Updated Main Application (`app/main.py`)

- **Environment Variable Logging**: Database URLs and sensitive environment variables are now sanitized before being logged
- **OAuth2 Callback Logging**: Sensitive information like state parameters, tokens, and error details are masked
- **Migration Logging**: Database credentials and sensitive migration output are sanitized
- **Logger Integration**: Replaced standard logger with `SanitizedLogger` for automatic sanitization

### 3. Updated CRUD Operations (`app/crud.py`)

- **User Operations**: Email addresses in all log messages are automatically sanitized
- **Authorization Logging**: User emails in authorization checks are masked
- **Logger Integration**: Replaced standard logger with `SanitizedLogger`

### 4. Updated Database Configuration (`alembic/env.py`)

- **Migration Comments**: Added comments indicating that sensitive URL construction is for internal use only and not logged
- **No Direct Logging**: The file doesn't directly log sensitive information

### 5. Created Test Suite (`tests/test_sanitization.py`)

Comprehensive test suite covering all sanitization functions to ensure they work correctly:
- Email sanitization tests
- URL sanitization tests
- Database URL sanitization tests
- Token sanitization tests
- Environment variable sanitization tests
- Log message sanitization tests

## Security Benefits

### Before Changes
```python
# Sensitive information was logged in plain text
logger.debug(f"User {email} accessed {url}")
logger.error(f"Database connection failed: {database_url}")
logger.info(f"OAuth2 token: {token}")
```

### After Changes
```python
# Sensitive information is automatically sanitized
logger.debug(f"User u**r@example.com accessed {url}")
logger.error(f"Database connection failed: mysql://user:***@localhost/db")
logger.info(f"OAuth2 token: eyJh...sw5c")
```

## Implementation Details

### Automatic Sanitization
The `SanitizedLogger` wrapper automatically sanitizes all log messages without requiring manual intervention:

```python
from app.utils import SanitizedLogger
logger = SanitizedLogger(logging.getLogger(__name__))

# All these calls are automatically sanitized
logger.info(f"User {email} logged in")  # Email is masked
logger.debug(f"Token: {jwt_token}")     # Token is masked
logger.error(f"DB error: {db_url}")     # DB URL is masked
```

### Pattern-Based Sanitization
The system uses regex patterns to automatically detect and sanitize:
- Email addresses: `\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b`
- JWT tokens: `\b[A-Za-z0-9-_]+\.[A-Za-z0-9-_]+\.[A-Za-z0-9-_]+\b`
- Database URLs: `(?:mysql|postgresql|sqlite)(?:\+[a-z]+)?://[^\s]+`

### Manual Sanitization
For specific cases, manual sanitization functions can be used:

```python
from app.utils import sanitize_email, sanitize_url

# Manual sanitization when needed
safe_email = sanitize_email(user_email)
safe_url = sanitize_url(oauth_url, ['code', 'state'])
```

## Testing

Run the sanitization tests to verify functionality:

```bash
uv run pytest tests/test_sanitization.py -v
```

## Best Practices

1. **Always use the SanitizedLogger**: Replace standard loggers with `SanitizedLogger` for automatic protection
2. **Manual sanitization for specific cases**: Use specific sanitization functions when needed
3. **Test sanitization**: Ensure new logging code doesn't expose sensitive information
4. **Review log output**: Regularly check logs to ensure no sensitive data is exposed

## Files Modified

- `app/utils.py` (new file)
- `app/main.py`
- `app/crud.py`
- `alembic/env.py`
- `tests/test_sanitization.py` (new file)

## Security Impact

These changes significantly improve the security posture of the application by:

1. **Preventing credential exposure** in logs
2. **Protecting user privacy** by masking email addresses
3. **Securing OAuth2 flows** by masking tokens and codes
4. **Protecting database credentials** in connection strings
5. **Maintaining audit trails** while removing sensitive data

The sanitization is automatic and comprehensive, reducing the risk of accidental exposure of sensitive information in logs. 