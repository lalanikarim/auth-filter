# AuthFilter

AuthFilter is a FastAPI-based authorization gateway for managing and enforcing access control to web resources based on user groups and URL groups. It supports OAuth2/OIDC authentication (provider-agnostic) and provides a simple UI and API for managing users, groups, URLs, and authorization rules.

## Features
- **OAuth2/OIDC Authentication**: Login via any OIDC-compliant provider (Google, Auth0, Okta, Azure AD, etc.)
- **User & URL Group Management**: Organize users and URLs into groups for flexible access control
- **Many-to-Many Associations**: Link user groups to URL groups to define access rules
- **Authorization API**: Check if a user is allowed to access a given URL
- **Jinja2 UI**: Simple web interface for managing users, groups, and associations
- **SQLite (default) or any SQLAlchemy-supported DB**

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
DATABASE_URL=sqlite+aiosqlite:///./authfilter.db
APP_ENV=development  # Set to 'production' for secure cookies (see below)
ALLOWED_WEB_ASSET_EXTENSIONS=css,js,png,jpg,jpeg,gif,svg,ico,woff,woff2,ttf,eot,map
```

### 4. Run the App
```bash
uvicorn app.main:app --reload
```

Visit [http://localhost:8000](http://localhost:8000) in your browser.

## Usage

### Authentication Flow
- Go to `/auth/login` to start the OAuth2 login flow.
- After login, cookies are set for authentication and user email.

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

## Database
- Uses SQLite by default (file: `authfilter.db`)
- Tables: `users`, `user_groups`, `urls`, `url_groups`, `user_group_url_group_associations`
- See `design-spec.md` for schema details

## Environment Variables
All OAuth2/OIDC and DB settings are configured via `.env` (see above).

- `APP_ENV=production` will set cookies with `secure=True` (required for HTTPS deployments). Use `APP_ENV=development` for local testing (cookies will be set with `secure=False`).
- `ALLOWED_WEB_ASSET_EXTENSIONS` is a comma-separated list of file extensions that should bypass authentication/authorization checks (default: `css,js,png,jpg,jpeg,gif,svg,ico,woff,woff2,ttf,eot,map`). Web assets can be accessed without any authentication.

## Development & Testing
- Run tests with:
  ```bash
  pytest
  ```
- Code is modular, with routers in `app/api/endpoints/`

## Security Notes
- Never commit your `.env` file (it's in `.gitignore`)
- Set `APP_ENV=production` and use HTTPS in production to ensure cookies are secure

## License
MIT
