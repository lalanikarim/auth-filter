# AuthFilter

AuthFilter is a FastAPI-based authorization gateway for managing and enforcing access control to web resources based on user groups and URL groups. It supports OAuth2/OIDC authentication (provider-agnostic) and provides a simple UI and API for managing users, groups, URLs, and authorization rules.

## Features

- **OAuth2/OIDC Authentication**: Login via any OIDC-compliant provider (Google, Auth0, Okta, Azure AD, etc.)
- **User & URL Group Management**: Organize users and URLs into groups for flexible access control
- **Many-to-Many Associations**: Link user groups to URL groups to define access rules
- **Authorization API**: Check if a user is allowed to access a given URL
- **Jinja2 UI**: Simple web interface for managing users, groups, and associations
- **SQLite (default) or any SQLAlchemy-supported DB**: Supports MySQL, PostgreSQL, and SQLite
- **Security-First Design**: Automatic log sanitization to prevent sensitive data exposure
- **Docker/Podman Support**: Containerized deployment with build and push scripts
- **Database Migrations**: Alembic-based schema management
- **Comprehensive Testing**: Full test suite with async support

## Architecture

### Core Components

- **Models** (`app/models.py`): SQLAlchemy ORM models for Users, UserGroups, URLs, URLGroups, and associations
- **CRUD Operations** (`app/crud.py`): Database operations with automatic log sanitization
- **API Endpoints** (`app/api/endpoints/`): RESTful API for all operations
- **Web UI** (`app/templates/`): Jinja2-based management interface
- **Security Utils** (`app/utils.py`): Comprehensive sanitization utilities for logs and sensitive data

### Database Schema

- **users**: User accounts with email addresses
- **user_groups**: Groups to organize users
- **user_group_members**: Many-to-many relationship between users and user groups
- **url_groups**: Groups to organize URL paths
- **urls**: Individual URL paths belonging to URL groups
- **user_group_url_group_associations**: Many-to-many relationship between user groups and URL groups

### Special Groups

The system automatically creates and manages special groups:

- **Internal User Group**: Superuser access to all URLs
- **Everyone**: Public URLs accessible without authentication
- **Authenticated**: URLs accessible to any logged-in user

## Quick Start

### 1. Prerequisite: Install [uv](https://github.com/astral-sh/uv)
```bash
pip install uv
```

### 2. Clone & Install
```bash
git clone https://github.com/yourusername/authfilter.git
cd authfilter
uv venv
source .venv/bin/activate
uv pip install .
```

### 3. Configure Environment
Create a `.env` file in the project root:
```ini
# OAuth2/OIDC Configuration
OAUTH2_CLIENT_ID=your-client-id
OAUTH2_CLIENT_SECRET=your-client-secret
OAUTH2_AUTH_URL=https://your-provider.com/oauth2/v2/auth
OAUTH2_TOKEN_URL=https://your-provider.com/oauth2/token
OAUTH2_JWKS_URL=https://your-provider.com/.well-known/jwks.json
OAUTH2_AUDIENCE=your-client-id
OAUTH2_ISSUER=https://your-provider.com
OAUTH2_COOKIE_NAME=auth_token
OAUTH2_SCOPE=openid email profile
OAUTH2_REDIRECT_URI=http://localhost:8000/auth/callback

# Database Configuration
DATABASE_URL=sqlite+aiosqlite:///./authfilter.db
# For MySQL: DATABASE_URL=mysql+aiomysql://user:password@localhost:3306/authfilter
# For PostgreSQL: DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/authfilter

# Application Settings
APP_ENV=development  # Set to 'production' for secure cookies
ALLOWED_WEB_ASSET_EXTENSIONS=css,js,png,jpg,jpeg,gif,svg,ico,woff,woff2,ttf,eot,map

# Container Registry (for deployment)
REGISTRY_URL=localhost:5000/k8s/auth-filter
CONTAINER_TOOL=podman  # or docker
```

### 4. Run Database Migrations
```bash
uv run migrate
```

### 5. Start the Application
```bash
uv run dev
```

Visit [http://localhost:8000](http://localhost:8000) in your browser.

## Usage

### Authentication Flow
1. Go to `/auth/login` to start the OAuth2 login flow
2. After successful authentication, cookies are set for `auth_token` and `x-auth-email`
3. Users are automatically added to the system upon first login

### Authorization API
- **Check access:**
  ```
  GET /api/authorize?url=/some/path
  (Requires x-auth-email cookie set by login)
  ```
  **Response:**
  ```json
  { "allowed": true }
  ```

### Management UI
- `/user-groups` — Manage user groups and their members
- `/url-groups` — Manage URL groups and their URLs
- `/associations` — Link user groups to URL groups
- `/authorize` — Manual authorization check UI (no authentication required)

### Web Assets
Static files with extensions defined in `ALLOWED_WEB_ASSET_EXTENSIONS` automatically bypass authentication and authorization checks.

## Development & Testing

### Running Tests
```bash
uv run test
```

### Development Server
```bash
uv run dev
```

### Database Migrations
```bash
# Create new migration
uv run alembic revision --autogenerate -m "description"

# Apply migrations
uv run migrate

# Downgrade last migration
uv run alembic downgrade -1
```

## Deployment

### Container Build & Push
```bash
# Build and push to registry
uv run build-and-push-image

# Push existing image
uv run push-image

# Retag for different environments
uv run retag-latest staging-registry.example.com/k8s/auth-filter
```

### Environment Variables
- `APP_ENV=production` will set cookies with `secure=True` (required for HTTPS deployments)
- `ALLOWED_WEB_ASSET_EXTENSIONS` is a comma-separated list of file extensions that bypass auth checks
- `REGISTRY_URL` and `CONTAINER_TOOL` for container deployment

## Security Features

### Log Sanitization
The application automatically sanitizes sensitive information in logs:
- Email addresses are masked (e.g., "user@example.com" → "u**r@example.com")
- Database URLs have credentials masked
- OAuth2 tokens and codes are partially masked
- JWT tokens show only first/last few characters

### Protected Groups
Special groups (`Internal User Group`, `Everyone`, `Authenticated`) are protected from deletion and provide system-wide access control.

### Web Asset Bypass
Static files (CSS, JS, images, etc.) automatically bypass authentication for performance.

## API Reference

### Authentication Endpoints
- `GET /auth/login` - Initiate OAuth2 login
- `GET /auth/callback` - OAuth2 callback handler
- `GET /logout` - Clear authentication cookies

### Authorization Endpoints
- `GET /api/authorize?url=<path>` - Check if user can access URL

### Management Endpoints
- `POST /api/user-groups` - Create user group
- `POST /api/user-groups/{id}/users` - Add user to group
- `POST /api/url-groups` - Create URL group
- `POST /api/url-groups/{id}/urls` - Add URL to group
- `POST /api/associations` - Link user group to URL group

## License
MIT
