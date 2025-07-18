# AuthFilter - Context7 Context File

## Project Overview

AuthFilter is a FastAPI-based authorization gateway that provides fine-grained access control to web resources through user groups and URL groups. It's designed as a lightweight, containerized service that can be deployed as a sidecar or standalone authorization service.

## Core Architecture

### Technology Stack
- **Framework**: FastAPI with async/await support
- **Database**: SQLAlchemy ORM with async support (SQLite, MySQL, PostgreSQL)
- **Authentication**: OAuth2/OIDC provider-agnostic
- **UI**: Jinja2 templates with HTMX for dynamic interactions
- **Container**: Docker/Podman with multi-stage builds
- **Package Management**: uv (modern Python package manager)
- **Migrations**: Alembic for database schema management
- **Testing**: pytest with async support

### Key Design Principles
1. **Security-First**: Automatic log sanitization, protected system groups
2. **Provider-Agnostic**: Works with any OIDC-compliant provider
3. **Flexible Authorization**: Many-to-many relationships between users and URLs
4. **Performance**: Web asset bypass, async database operations
5. **Container-Ready**: Optimized for Kubernetes deployment

## Database Schema

### Core Entities
```sql
-- Users and Groups
users (user_id, email, created_at)
user_groups (group_id, name, created_at, protected)
user_group_members (user_group_id, user_id) -- Many-to-many

-- URLs and Groups  
url_groups (group_id, name, created_at, protected)
urls (url_id, path, url_group_id)

-- Authorization Rules
user_group_url_group_associations (user_group_id, url_group_id) -- Many-to-many
```

### Special System Groups
- **Internal User Group**: Superuser access (protected)
- **Everyone**: Public URLs, no auth required (protected)
- **Authenticated**: Any logged-in user access (protected)

## API Endpoints

### Authentication Flow
```
GET /auth/login → OAuth2 provider → GET /auth/callback → Set cookies
```

### Authorization API
```
GET /api/authorize?url=<path>
Headers: x-auth-email cookie (set by login)
Response: {"allowed": true/false}
```

### Management APIs
- User Groups: CRUD operations for user organization
- URL Groups: CRUD operations for URL organization  
- Associations: Link user groups to URL groups
- Web UI: Jinja2 templates for management interface

## Security Implementation

### Log Sanitization (`app/utils.py`)
- **Email Masking**: `user@example.com` → `u**r@example.com`
- **URL Sanitization**: Masks sensitive query parameters
- **Token Masking**: JWT tokens show first/last 4 chars
- **Database URL Masking**: Credentials hidden in connection strings
- **Automatic Sanitization**: `SanitizedLogger` wrapper for all logging

### Authorization Logic (`app/crud.py`)
1. **Web Asset Check**: Static files bypass auth based on extension
2. **Public Access**: URLs in "Everyone" group
3. **Authenticated Access**: URLs in "Authenticated" group + logged-in user
4. **Superuser Access**: Users in "Internal User Group"
5. **Group-Based Access**: User group → URL group associations

### Protected Resources
- System groups cannot be deleted
- Web assets automatically bypass authentication
- Sensitive data never logged in plain text

## Configuration Management

### Environment Variables
```bash
# OAuth2/OIDC
OAUTH2_CLIENT_ID, OAUTH2_CLIENT_SECRET
OAUTH2_AUTH_URL, OAUTH2_TOKEN_URL, OAUTH2_JWKS_URL
OAUTH2_AUDIENCE, OAUTH2_ISSUER, OAUTH2_COOKIE_NAME
OAUTH2_SCOPE, OAUTH2_REDIRECT_URI

# Database
DATABASE_URL (supports SQLite, MySQL, PostgreSQL)

# Application
APP_ENV (development/production)
ALLOWED_WEB_ASSET_EXTENSIONS

# Container Deployment
REGISTRY_URL, CONTAINER_TOOL
```

### Database Support
- **SQLite**: Default for development (`sqlite+aiosqlite:///./authfilter.db`)
- **MySQL**: Production-ready (`mysql+aiomysql://user:pass@host:3306/db`)
- **PostgreSQL**: Production-ready (`postgresql+asyncpg://user:pass@host:5432/db`)

## Development Workflow

### Local Development
```bash
uv venv && source .venv/bin/activate
uv pip install .
uv run migrate  # Run database migrations
uv run dev      # Start development server
```

### Testing
```bash
uv run test                    # Run all tests
uv run pytest --watch         # Watch mode
uv run pytest tests/test_api.py  # Specific test file
```

### Database Migrations
```bash
uv run alembic revision --autogenerate -m "description"
uv run migrate
uv run alembic downgrade -1
```

## Container Deployment

### Build System (`scripts/`)
- **build_image.py**: Smart tag generation with date/build number
- **push_image.py**: Push to registry with latest tag
- **build_and_push_image.py**: Combined build and push
- **retag_latest.py**: Retag for different environments

### Container Features
- Multi-stage build for optimization
- Non-root user support (commented)
- Python 3.13 slim base image
- uv package manager for fast installs

### Deployment Commands
```bash
uv run build-and-push-image
uv run push-image
uv run retag-latest staging-registry.example.com/k8s/auth-filter
```

## Integration Patterns

### As Authorization Gateway
1. **Sidecar Pattern**: Deploy alongside applications
2. **API Gateway**: Centralized authorization service
3. **Reverse Proxy**: Nginx/Apache with auth subrequests

### OAuth2 Provider Integration
- **Google**: Standard OIDC endpoints
- **Auth0**: Custom domain support
- **Okta**: Enterprise SSO
- **Azure AD**: Microsoft identity platform
- **Custom**: Any OIDC-compliant provider

### Database Integration
- **Alembic Migrations**: Schema versioning
- **Async Operations**: Non-blocking database calls
- **Connection Pooling**: Optimized for high concurrency
- **Transaction Management**: ACID compliance

## Performance Considerations

### Web Asset Optimization
- Static files bypass authentication checks
- Configurable extensions list
- No database queries for static resources

### Database Optimization
- Async SQLAlchemy operations
- Connection pooling
- Indexed foreign keys
- Efficient many-to-many queries

### Caching Strategy
- No built-in caching (stateless design)
- Suitable for Redis/Memcached integration
- Cookie-based session management

## Monitoring and Observability

### Logging
- Structured logging with sanitization
- Debug, info, warning, error levels
- Sensitive data automatically masked
- Request/response logging

### Health Checks
- Database connectivity
- OAuth2 provider availability
- Application status endpoints

### Metrics
- Authorization request counts
- Response times
- Error rates
- Database connection status

## Security Best Practices

### Authentication
- OAuth2/OIDC standard compliance
- Secure cookie handling
- CSRF protection
- Session management

### Authorization
- Principle of least privilege
- Group-based access control
- Protected system groups
- Audit trail capability

### Data Protection
- Log sanitization
- No sensitive data in logs
- Secure environment variable handling
- Database credential protection

## Troubleshooting

### Common Issues
1. **OAuth2 Configuration**: Verify provider endpoints and credentials
2. **Database Connection**: Check DATABASE_URL format and connectivity
3. **Migration Errors**: Ensure database schema is up to date
4. **Container Build**: Verify registry access and credentials

### Debug Mode
- Set logging level to DEBUG
- Check sanitized logs for sensitive data
- Verify environment variable loading
- Test database connectivity

## Future Enhancements

### Potential Features
- Redis caching integration
- Prometheus metrics
- OpenTelemetry tracing
- Multi-tenant support
- API rate limiting
- Audit logging
- Webhook notifications

### Scalability Considerations
- Horizontal scaling with stateless design
- Database read replicas
- Load balancer integration
- Kubernetes operator
- Helm charts for deployment

## Code Quality

### Testing Strategy
- Unit tests for CRUD operations
- Integration tests for API endpoints
- Sanitization utility tests
- Async test support

### Code Standards
- Type hints throughout
- Async/await patterns
- Error handling
- Security-first approach
- Comprehensive documentation

This context file provides a complete understanding of the AuthFilter project for context engineering, development, deployment, and maintenance purposes. 