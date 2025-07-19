from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request, Form, Depends, status, Body, Cookie, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from .db import get_engine, Base
import asyncio
from app.api.endpoints import auth_router
from app.api.endpoints import user_groups_router
from app.api.endpoints import url_groups_router
from app.api.endpoints import associations_router
from app.api.endpoints import authorize_router
from app.api.endpoints import applications_router
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends
from app.db import get_async_session
from app import crud
from app.schemas import UserGroupCreate, UserCreate
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from collections import defaultdict
from sqlalchemy import delete
from app.models import user_group_members, Url
from app.models import UserGroup, UrlGroup
import os
import requests
from urllib.parse import urlencode, quote, unquote, urlparse
from jose import jwt, JWTError
import json
import time
import logging


OAUTH2_CLIENT_ID = os.getenv("OAUTH2_CLIENT_ID", "your-client-id")
OAUTH2_CLIENT_SECRET = os.getenv("OAUTH2_CLIENT_SECRET", "your-client-secret")
OAUTH2_AUTH_URL = os.getenv("OAUTH2_AUTH_URL", "https://example.com/oauth2/v2/auth")
OAUTH2_TOKEN_URL = os.getenv("OAUTH2_TOKEN_URL", "https://example.com/oauth2/token")
OAUTH2_JWKS_URL = os.getenv("OAUTH2_JWKS_URL", "https://example.com/.well-known/jwks.json")
OAUTH2_AUDIENCE = os.getenv("OAUTH2_AUDIENCE", OAUTH2_CLIENT_ID)
OAUTH2_ISSUER = os.getenv("OAUTH2_ISSUER", "https://example.com")
COOKIE_NAME = os.getenv("OAUTH2_COOKIE_NAME", "auth_token")
REDIRECT_URI = os.getenv("OAUTH2_REDIRECT_URI", "http://localhost:8000/auth/callback")
OAUTH2_SCOPE = os.getenv("OAUTH2_SCOPE", "openid email profile")

app = FastAPI()

# Mount static files (for htmx, shadcn, CSS, JS)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Set up Jinja2 templates
templates = Jinja2Templates(directory="app/templates")

logger = logging.getLogger("authfilter")
logging.basicConfig(level=logging.DEBUG)

# Use sanitized logger to automatically mask sensitive information
from app.utils import SanitizedLogger, sanitize_url, sanitize_email
logger = SanitizedLogger(logger)

@app.on_event("startup")
async def on_startup():
    # Auto-create tables in dev (SQLite). In prod, use Alembic for migrations.
    # if engine.url.drivername.startswith("sqlite"):
    #     async with engine.begin() as conn:
    #         await conn.run_sync(Base.metadata.create_all)

    # Debug: Print environment variables (sanitized)
    run_migrations_env = os.getenv("RUN_MIGRATIONS", "false")
    database_url = os.getenv("DATABASE_URL", "not set")
    from app.utils import sanitize_database_url
    print(f"DEBUG: RUN_MIGRATIONS = {run_migrations_env}")
    print(f"DEBUG: DATABASE_URL = {sanitize_database_url(database_url)}")
    
    # Run migrations if explicitly requested
    if run_migrations_env.lower() == "true":
        print("DEBUG: Running migrations...")
        await run_migrations()
    else:
        print("DEBUG: Skipping migrations (RUN_MIGRATIONS != 'true')")

    # Ensure internal groups exist
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.future import select
    from app.models import UserGroup, UrlGroup
    from sqlalchemy.orm import sessionmaker

    # Use an async session for startup
    from app.db import get_async_session_maker
    async_session = get_async_session_maker()
    async with async_session() as session:
        # Internal User Group
        internal_user_group_name = "Internal User Group"
        q = await session.execute(select(UserGroup).where(UserGroup.name == internal_user_group_name))
        group = q.scalar_one_or_none()
        if not group:
            session.add(UserGroup(name=internal_user_group_name, protected=1))
        elif not group.protected:
            group.protected = 1
        # Everyone Url Group
        everyone_url_group_name = "Everyone"
        q = await session.execute(select(UrlGroup).where(UrlGroup.name == everyone_url_group_name))
        group = q.scalar_one_or_none()
        if not group:
            session.add(UrlGroup(name=everyone_url_group_name, protected=1))
        elif not group.protected:
            group.protected = 1
        # Authenticated Url Group
        authenticated_url_group_name = "Authenticated"
        q = await session.execute(select(UrlGroup).where(UrlGroup.name == authenticated_url_group_name))
        group = q.scalar_one_or_none()
        if not group:
            session.add(UrlGroup(name=authenticated_url_group_name, protected=1))
        elif not group.protected:
            group.protected = 1
        await session.commit()

async def run_migrations():
    """Run Alembic migrations if requested via environment variable."""
    import subprocess
    import sys
    try:
        print("Running Alembic migrations...")
        print(f"DEBUG: Current working directory: {os.getcwd()}")
        print(f"DEBUG: Environment variables in subprocess:")
        from app.utils import sanitize_environment_variables
        sensitive_env_vars = {k: v for k, v in os.environ.items() 
                            if k in ['RUN_MIGRATIONS', 'DATABASE_URL', 'DB_USER', 'DB_PASSWORD', 'DB_HOST', 'DB_PORT', 'DB_NAME']}
        sanitized_env_vars = sanitize_environment_variables(sensitive_env_vars)
        for key, value in sanitized_env_vars.items():
            print(f"  {key} = {value}")
        
        result = subprocess.run(
            ["uv", "run", "alembic", "upgrade", "head"],
            capture_output=True,
            text=True,
            check=True,
            env=os.environ.copy()  # Pass current environment variables including those from .env
        )
        print("Migrations completed successfully")
        print(f"Output: {result.stdout}")
    except subprocess.CalledProcessError as e:
        print(f"Migration failed: {e}")
        # Sanitize stdout/stderr to avoid logging sensitive information
        from app.utils import sanitize_log_message
        print(f"stdout: {sanitize_log_message(e.stdout)}")
        print(f"stderr: {sanitize_log_message(e.stderr)}")
        print("Exiting application due to migration failure")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error during migration: {e}")
        import traceback
        traceback.print_exc()
        print("Exiting application due to migration error")
        sys.exit(1)

@app.get("/", response_class=HTMLResponse)
async def root(request: Request, session: AsyncSession = Depends(get_async_session)):
    """Dashboard page with links to all sections."""
    # Get some basic stats
    app_count = (await session.execute(text("SELECT COUNT(*) FROM applications"))).scalar()
    user_group_count = (await session.execute(text("SELECT COUNT(*) FROM user_groups"))).scalar()
    url_group_count = (await session.execute(text("SELECT COUNT(*) FROM url_groups"))).scalar()
    user_count = (await session.execute(text("SELECT COUNT(*) FROM users"))).scalar()
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "app_count": app_count,
        "user_group_count": user_group_count,
        "url_group_count": url_group_count,
        "user_count": user_count
    })

@app.get("/user-groups", response_class=HTMLResponse)
async def user_groups(request: Request, session: AsyncSession = Depends(get_async_session)):
    """User groups page."""
    groups = await crud.get_all_user_groups(session)
    
    # Add user count to each group
    for group in groups:
        group.user_count = await crud.get_user_count_in_group(session, group.group_id)
    
    return templates.TemplateResponse("user_groups.html", {
        "request": request,
        "groups": groups
    })

@app.get("/user-groups/create-form", response_class=HTMLResponse)
async def user_groups_create_form(request: Request):
    """Get the user group creation form."""
    return templates.TemplateResponse("partials/user_groups_create_form.html", {
        "request": request
    })

@app.post("/user-groups", response_class=HTMLResponse)
async def create_user_group_ui(
    request: Request, 
    name: str = Form(...), 
    session: AsyncSession = Depends(get_async_session)
):
    """Create a new user group via UI."""
    try:
        await crud.create_user_group(session, name)
        groups = await crud.get_all_user_groups(session)
        
        # Add user count to each group
        for group in groups:
            group.user_count = await crud.get_user_count_in_group(session, group.group_id)
        
        return templates.TemplateResponse("partials/user_groups_list.html", {
            "request": request, 
            "groups": groups
        })
    except ValueError as e:
        # Return error message
        return HTMLResponse(f"<div class='text-red-600 p-4'>{str(e)}</div>")

@app.get("/user-groups/{group_id}", response_class=HTMLResponse)
async def user_group_detail(
    request: Request, 
    group_id: int, 
    session: AsyncSession = Depends(get_async_session)
):
    """User group detail page."""
    group = await crud.get_user_group(session, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="User group not found")
    
    # Get users in the group
    users = await crud.get_users_in_group(session, group_id)
    
    # Get associated URL groups
    url_groups = []
    if group.name != 'Internal User Group':
        url_groups = await crud.get_url_groups_for_user_group(session, group_id)
    
    return templates.TemplateResponse("user_group_detail.html", {
        "request": request, 
        "group": group,
        "users": users,
        "url_groups": url_groups
    })

@app.get("/user-groups/{group_id}/edit-form", response_class=HTMLResponse)
async def user_groups_edit_form(
    request: Request, 
    group_id: int, 
    session: AsyncSession = Depends(get_async_session)
):
    """Get the user group edit form."""
    group = await crud.get_user_group(session, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="User group not found")
    
    return templates.TemplateResponse("partials/user_groups_edit_form.html", {
        "request": request, 
        "group": group
    })

@app.put("/user-groups/{group_id}", response_class=HTMLResponse)
async def update_user_group_ui(
    request: Request, 
    group_id: int,
    name: str = Form(...), 
    session: AsyncSession = Depends(get_async_session)
):
    """Update a user group via UI."""
    try:
        await crud.update_user_group(session, group_id, name=name)
        
        # Check if we're on the detail page by looking for a specific header
        referer = request.headers.get("referer", "")
        if f"/user-groups/{group_id}" in referer:
            # We're on the detail page, return empty response
            return HTMLResponse("")
        else:
            # We're on the list page, return the updated list
            groups = await crud.get_all_user_groups(session)
            
            # Add user count to each group
            for group in groups:
                group.user_count = await crud.get_user_count_in_group(session, group.group_id)
            
            return templates.TemplateResponse("partials/user_groups_list.html", {
                "request": request, 
                "groups": groups
            })
    except ValueError as e:
        # Return error message
        return HTMLResponse(f"<div class='text-red-600 p-4'>{str(e)}</div>")

@app.delete("/user-groups/{group_id}", response_class=HTMLResponse)
async def delete_user_group_ui(
    request: Request, 
    group_id: int, 
    session: AsyncSession = Depends(get_async_session)
):
    """Delete a user group via UI."""
    success = await crud.delete_user_group(session, group_id)
    if not success:
        raise HTTPException(status_code=404, detail="User group not found")
    
    groups = await crud.get_all_user_groups(session)
    
    # Add user count to each group
    for group in groups:
        group.user_count = await crud.get_user_count_in_group(session, group.group_id)
    
    return templates.TemplateResponse("partials/user_groups_list.html", {
        "request": request, 
        "groups": groups
    })

@app.get("/user-groups/{group_id}/add-user-form", response_class=HTMLResponse)
async def user_groups_add_user_form(
    request: Request, 
    group_id: int, 
    session: AsyncSession = Depends(get_async_session)
):
    """Get the add user form for a user group."""
    group = await crud.get_user_group(session, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="User group not found")
    
    return templates.TemplateResponse("partials/user_groups_add_user_form.html", {
        "request": request, 
        "group": group
    })

@app.post("/user-groups/{group_id}/add-user", response_class=HTMLResponse)
async def add_user_to_group_ui(
    request: Request, 
    group_id: int, 
    email: str = Form(...), 
    session: AsyncSession = Depends(get_async_session)
):
    """Add a user to a group via UI."""
    try:
        # Validate input
        if not email or not email.strip():
            return HTMLResponse("<div class='text-red-600 p-4'>Error: Email cannot be empty</div>")
        
        email = email.strip()
        
        # Check if user already exists in this group
        existing_user = await session.execute(
            text("""
                SELECT u.email FROM users u 
                JOIN user_group_members ugm ON u.user_id = ugm.user_id 
                WHERE ugm.user_group_id = :group_id AND u.email = :email
            """),
            {"group_id": group_id, "email": email}
        )
        
        if existing_user.fetchone():
            return HTMLResponse("<div class='text-red-600 p-4'>Error: User already exists in this group</div>")
        
        # Get the group to check if it exists
        group = await crud.get_user_group(session, group_id)
        if not group:
            return HTMLResponse("<div class='text-red-600 p-4'>Error: User group not found</div>")
        
        # Ensure user exists or create
        db_user = await crud.get_user(session, email)
        if not db_user:
            await crud.create_user(session, email)
        await crud.add_user_to_group(session, group_id, email)
        
        # Return updated users list
        users = await crud.get_users_in_group(session, group_id)
        
        return templates.TemplateResponse("partials/users_list.html", {
            "request": request, 
            "users": users,
            "group": group
        })
    except ValueError as e:
        return HTMLResponse(f"<div class='text-red-600 p-4'>Error: {str(e)}</div>")
    except Exception as e:
        return HTMLResponse(f"<div class='text-red-600 p-4'>Error: An unexpected error occurred while adding the user</div>")

@app.delete("/user-groups/{group_id}/remove-user", response_class=HTMLResponse)
async def remove_user_from_group_ui(
    request: Request, 
    group_id: int, 
    email: str = Form(...), 
    session: AsyncSession = Depends(get_async_session)
):
    """Remove a user from a group via UI."""
    try:
        # First get the user by email
        user = await crud.get_user(session, email)
        if user:
            await session.execute(delete(user_group_members).where(user_group_members.c.user_group_id == group_id, user_group_members.c.user_id == user.user_id))
            await session.commit()
        
        # Return updated users list
        users = await crud.get_users_in_group(session, group_id)
        group = await crud.get_user_group(session, group_id)
        
        return templates.TemplateResponse("partials/users_list.html", {
            "request": request, 
            "users": users,
            "group": group
        })
    except Exception as e:
        return HTMLResponse(f"<div class='text-red-600 p-4'>Error: An unexpected error occurred while removing the user</div>")

@app.post("/user-groups/{group_id}/delete")
async def delete_user_group(request: Request, group_id: int, session: AsyncSession = Depends(get_async_session)):
    # Prevent deletion if protected
    group = await session.get(UserGroup, group_id)
    if group and getattr(group, 'protected', False):
        return RedirectResponse(url="/user-groups", status_code=status.HTTP_303_SEE_OTHER)
    # Only allow deletion if there are no associations
    assoc_count = (await session.execute(text("SELECT COUNT(*) FROM user_group_url_group_associations WHERE user_group_id = :gid"), {"gid": group_id})).scalar()
    if assoc_count == 0:
        await session.execute(delete(UserGroup).where(UserGroup.group_id == group_id))
        await session.commit()
    return RedirectResponse(url="/user-groups", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/url-groups")
async def url_groups(request: Request, session: AsyncSession = Depends(get_async_session)):
    selected = request.query_params.get("selected")
    result = await session.execute(text("SELECT group_id, name FROM url_groups ORDER BY group_id"))
    groups = result.fetchall()
    # Fetch urls in each group
    url_map = defaultdict(list)
    url_rows = await session.execute(text("SELECT url_group_id, path FROM urls ORDER BY url_group_id, path"))
    for row in url_rows:
        url_map[row.url_group_id].append(row.path)
    # Fetch associations for delete button logic and for user group lookup
    assoc_rows = await session.execute(text('''
        SELECT a.user_group_id, a.url_group_id
        FROM user_group_url_group_associations a
    '''))
    associations = assoc_rows.fetchall()
    associated_url_group_ids = set(row.url_group_id for row in associations)
    # Fetch all user groups
    user_group_rows = await session.execute(text("SELECT group_id, name FROM user_groups ORDER BY group_id"))
    user_groups = user_group_rows.fetchall()
    # Prepare selected group data
    selected_group = None
    selected_group_urls = []
    selected_group_user_group_ids = []
    selected_group_user_groups = []
    if selected:
        try:
            selected_id = int(selected)
            selected_group = next((g for g in groups if g.group_id == selected_id), None)
            if selected_group:
                selected_group_urls = url_map.get(selected_id, [])
                selected_group_user_group_ids = [a.user_group_id for a in associations if a.url_group_id == selected_id]
                selected_group_user_groups = [g for g in user_groups if g.group_id in selected_group_user_group_ids]
        except Exception:
            selected_group = None
    return templates.TemplateResponse("url_groups.html", {
        "request": request,
        "groups": groups,
        "urls_in_group": url_map,
        "associations": associations,
        "associated_url_group_ids": associated_url_group_ids,
        "user_groups": user_groups,
        "selected_group": selected_group,
        "selected_group_urls": selected_group_urls,
        "selected_group_user_groups": selected_group_user_groups,
        "selected": selected
    })

@app.post("/url-groups")
async def create_url_group(request: Request, name: str = Form(...), session: AsyncSession = Depends(get_async_session)):
    from sqlalchemy.exc import IntegrityError
    try:
        group = await crud.create_url_group(session, name)
        group_id = group.group_id
    except IntegrityError:
        await session.rollback()
        group_id = None
        # Optionally, add flash message logic here
    if group_id:
        return RedirectResponse(url=f"/url-groups?selected={group_id}", status_code=status.HTTP_303_SEE_OTHER)
    return RedirectResponse(url="/url-groups", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/url-groups/{group_id}/add-url")
async def add_url_to_group(request: Request, group_id: int, path: str = Form(...), session: AsyncSession = Depends(get_async_session)):
    # Ensure URL exists or create
    db_url = await crud.get_url(session, path)
    if not db_url:
        await crud.create_url(session, path, group_id)
    else:
        await crud.add_url_to_group(session, group_id, path)
    return RedirectResponse(url=f"/url-groups?selected={group_id}", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/url-groups/{group_id}/remove-url")
async def remove_url_from_group(request: Request, group_id: int, path: str = Form(...), session: AsyncSession = Depends(get_async_session)):
    await session.execute(delete(Url).where(Url.url_group_id == group_id, Url.path == path))
    await session.commit()
    return RedirectResponse(url=f"/url-groups?selected={group_id}", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/url-groups/{group_id}/delete")
async def delete_url_group(request: Request, group_id: int, session: AsyncSession = Depends(get_async_session)):
    # Prevent deletion if protected
    group = await session.get(UrlGroup, group_id)
    if group and getattr(group, 'protected', False):
        return RedirectResponse(url="/url-groups", status_code=status.HTTP_303_SEE_OTHER)
    # Only allow deletion if there are no associations
    assoc_count = (await session.execute(text("SELECT COUNT(*) FROM user_group_url_group_associations WHERE url_group_id = :gid"), {"gid": group_id})).scalar()
    if assoc_count == 0:
        await session.execute(delete(UrlGroup).where(UrlGroup.group_id == group_id))
        await session.commit()
    return RedirectResponse(url="/url-groups", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/associations")
async def associations(request: Request, session: AsyncSession = Depends(get_async_session)):
    sort = request.query_params.get("sort", "user_group")
    order = request.query_params.get("order", "asc")
    # Get all associations with group names
    result = await session.execute(text('''
        SELECT a.user_group_id, ug.name as user_group_name, a.url_group_id, ugg.name as url_group_name
        FROM user_group_url_group_associations a
        JOIN user_groups ug ON a.user_group_id = ug.group_id
        JOIN url_groups ugg ON a.url_group_id = ugg.group_id
    '''))
    associations = result.fetchall()
    # Sort in Python for flexibility
    reverse = (order == "desc")
    if sort == "user_group":
        associations = sorted(associations, key=lambda a: (a.user_group_name or ""), reverse=reverse)
    elif sort == "url_group":
        associations = sorted(associations, key=lambda a: (a.url_group_name or ""), reverse=reverse)
    user_groups = (await session.execute(text("SELECT group_id, name FROM user_groups ORDER BY name"))).fetchall()
    url_groups = (await session.execute(text("SELECT group_id, name FROM url_groups ORDER BY name"))).fetchall()
    return templates.TemplateResponse("associations.html", {
        "request": request,
        "associations": associations,
        "user_groups": user_groups,
        "url_groups": url_groups,
        "sort": sort,
        "order": order
    })

@app.post("/associations")
async def create_association(request: Request, user_group_id: int = Form(...), url_group_id: int = Form(...), redirect: str = Form(None), session: AsyncSession = Depends(get_async_session)):
    await crud.link_user_group_to_url_group(session, user_group_id, url_group_id)
    if redirect:
        return RedirectResponse(url=redirect, status_code=status.HTTP_303_SEE_OTHER)
    return RedirectResponse(url="/associations", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/associations/remove")
async def remove_association(request: Request, user_group_id: int = Form(...), url_group_id: int = Form(...), redirect: str = Form(None), session: AsyncSession = Depends(get_async_session)):
    from app.models import user_group_url_group_associations
    await session.execute(
        delete(user_group_url_group_associations).where(
            user_group_url_group_associations.c.user_group_id == user_group_id,
            user_group_url_group_associations.c.url_group_id == url_group_id
        )
    )
    await session.commit()
    if redirect:
        return RedirectResponse(url=redirect, status_code=status.HTTP_303_SEE_OTHER)
    return RedirectResponse(url="/associations", status_code=status.HTTP_303_SEE_OTHER)

# Helper to fetch and cache JWKS
_jwks_cache = None
_jwks_cache_time = 0
_JWKS_CACHE_TTL = 3600

def get_jwks():
    global _jwks_cache, _jwks_cache_time
    now = time.time()
    if _jwks_cache and (now - _jwks_cache_time) < _JWKS_CACHE_TTL:
        return _jwks_cache
    resp = requests.get(OAUTH2_JWKS_URL)
    resp.raise_for_status()
    _jwks_cache = resp.json()
    _jwks_cache_time = now
    return _jwks_cache

async def get_current_user_from_cookie(auth_token: str = Cookie(None)):
    if not auth_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    jwks = get_jwks()
    try:
        payload = jwt.decode(
            auth_token,
            jwks,
            algorithms=["RS256"],
            audience=OAUTH2_AUDIENCE,
            issuer=OAUTH2_ISSUER,
            options={"verify_at_hash": False}
        )
        return payload
    except JWTError as e:
        raise HTTPException(status_code=401, detail="Invalid token")

# /authorize UI - no authentication required
@app.get("/authorize", response_class=HTMLResponse)
async def authorize_page(request: Request):
    next_path = request.query_params.get("next", None)
    url_path = request.query_params.get("url_path", "")
    email = request.query_params.get("email", "")
    return templates.TemplateResponse("authorize.html", {"request": request, "allowed": None, "user": None, "next": next_path, "url_path": url_path, "email": email})

@app.post("/authorize", response_class=HTMLResponse)
async def authorize_check(request: Request, email: str = Form(None), url_path: str = Form(None), session: AsyncSession = Depends(get_async_session)):
    # Fallback to query string if not present in form
    if not url_path:
        url_path = request.query_params.get("url_path", "")
    if not email:
        email = request.query_params.get("email", "")
    
    # Use the new full URL authorization function
    from app.crud import is_user_allowed_full_url
    allowed = await is_user_allowed_full_url(session, email, url_path)
    
    return templates.TemplateResponse("authorize.html", {"request": request, "allowed": allowed, "email": email, "url_path": url_path, "user": None})

def is_safe_next_path(url: str) -> bool:
    return url.startswith("/") or url.startswith("http://") or url.startswith("https://")

@app.get("/auth/login")
def auth_login(request: Request):
    next_path = request.query_params.get("next", "/")
    logger.debug(f"/auth/login: received next param: {next_path}")
    if not is_safe_next_path(next_path):
        logger.debug(f"/auth/login: next_path '{next_path}' is not safe, defaulting to '/'")
        next_path = "/"
    else:
        logger.debug(f"/auth/login: using next_path: {next_path}")
    params = {
        "client_id": OAUTH2_CLIENT_ID,
        "response_type": "code",
        "scope": OAUTH2_SCOPE,
        "redirect_uri": REDIRECT_URI,
        "access_type": "offline",
        "prompt": "consent",
        "state": quote(next_path),
    }
    url = f"{OAUTH2_AUTH_URL}?{urlencode(params)}"
    logger.debug(f"/auth/login: redirecting to OAuth2 URL: {sanitize_url(url, ['code', 'state'])}")
    return RedirectResponse(url)

@app.get("/auth/callback")
def auth_callback(request: Request):
    code = request.query_params.get("code")
    state = request.query_params.get("state", "%2F")
    next_path = unquote(unquote(state))
    logger.debug(f"/auth/callback: received state param: ***, decoded next_path: {next_path}")
    if not is_safe_next_path(next_path):
        logger.debug(f"/auth/callback: next_path '{next_path}' is not safe, defaulting to '/'")
        next_path = "/"
    else:
        logger.debug(f"/auth/callback: using next_path: {next_path}")
    if not code:
        logger.error("/auth/callback: Missing code parameter")
        return HTMLResponse("Missing code", status_code=400)
    data = {
        "code": code,
        "client_id": OAUTH2_CLIENT_ID,
        "client_secret": OAUTH2_CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
    }
    logger.debug(f"/auth/callback: exchanging code for token at {sanitize_url(OAUTH2_TOKEN_URL)}")
    token_resp = requests.post(OAUTH2_TOKEN_URL, data=data)
    if not token_resp.ok:
        logger.error(f"/auth/callback: OAuth2 token exchange error: ***")
        return HTMLResponse("Token exchange failed", status_code=400)
    token_data = token_resp.json()
    id_token = token_data.get("id_token")
    if not id_token:
        logger.error("/auth/callback: No id_token in token response")
        return HTMLResponse("No id_token", status_code=400)
    # Extract email from id_token
    try:
        jwks = get_jwks()
        payload = jwt.decode(
            id_token,
            jwks,
            algorithms=["RS256"],
            audience=OAUTH2_AUDIENCE,
            issuer=OAUTH2_ISSUER,
            options={"verify_at_hash": False}
        )
        email = payload.get("email")
        if not email:
            logger.error("/auth/callback: No email in token payload")
            return HTMLResponse("No email in token", status_code=400)
        logger.debug(f"/auth/callback: extracted email: {sanitize_email(email)}")
    except Exception as e:
        logger.error(f"/auth/callback: Token decode error: ***")
        return HTMLResponse("Token decode error", status_code=400)
    # Determine cookie domain
    cookie_domain = None
    if next_path.startswith("http://") or next_path.startswith("https://"):
        parsed = urlparse(next_path)
        cookie_domain = parsed.hostname
        logger.debug(f"/auth/callback: setting cookie domain to {cookie_domain}")
    # Set cookies and redirect to next_path
    response = RedirectResponse(url=next_path)
    APP_ENV = os.getenv("APP_ENV", "development")
    COOKIE_SECURE = APP_ENV == "production"
    response.set_cookie(
        COOKIE_NAME,
        id_token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        max_age=3600,
        domain=cookie_domain
    )
    response.set_cookie(
        "x-auth-email",
        email,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        max_age=3600,
        domain=cookie_domain
    )
    logger.debug(f"/auth/callback: set cookies and redirecting to: {next_path}")
    return response

@app.get("/logout")
def logout():
    response = RedirectResponse(url="/")
    response.delete_cookie(COOKIE_NAME)
    return response

@app.get("/applications", response_class=HTMLResponse)
async def applications(request: Request, session: AsyncSession = Depends(get_async_session)):
    """Applications list page."""
    applications = await crud.get_all_applications_with_url_groups_count(session)
    return templates.TemplateResponse("applications.html", {
        "request": request, 
        "applications": applications
    })

@app.get("/applications/create-form", response_class=HTMLResponse)
async def applications_create_form(request: Request):
    """Get the application creation form."""
    return templates.TemplateResponse("partials/applications_create_form.html", {"request": request})

@app.post("/applications", response_class=HTMLResponse)
async def create_application_ui(
    request: Request, 
    name: str = Form(...), 
    host: str = Form(...), 
    description: str = Form(None),
    session: AsyncSession = Depends(get_async_session)
):
    """Create a new application via UI."""
    try:
        await crud.create_application(session, name=name, host=host, description=description)
        applications = await crud.get_all_applications_with_url_groups_count(session)
        return templates.TemplateResponse("partials/applications_list.html", {
            "request": request, 
            "applications": applications
        })
    except ValueError as e:
        # Return error message
        return HTMLResponse(f"<div class='text-red-600 p-4'>{str(e)}</div>")

@app.get("/applications/{app_id}", response_class=HTMLResponse)
async def application_detail(
    request: Request, 
    app_id: int, 
    session: AsyncSession = Depends(get_async_session)
):
    """Application detail page."""
    app = await crud.get_application(session, app_id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    
    # Get URL groups with their URLs in a single query to avoid lazy loading
    url_groups_result = await session.execute(
        text("""
            SELECT 
                ug.group_id, 
                ug.name, 
                ug.app_id,
                ug.created_at,
                ug.protected,
                u.path
            FROM url_groups ug
            LEFT JOIN urls u ON ug.group_id = u.url_group_id
            WHERE ug.app_id = :app_id
            ORDER BY ug.name, u.path
        """),
        {"app_id": app_id}
    )
    
    # Group the results by URL group
    url_groups_data = {}
    for row in url_groups_result.fetchall():
        group_id = row.group_id
        if group_id not in url_groups_data:
            url_groups_data[group_id] = {
                "group_id": group_id,
                "name": row.name,
                "app_id": row.app_id,
                "created_at": row.created_at,
                "protected": row.protected,
                "urls": []
            }
        if row.path:  # Only add if path is not None
            url_groups_data[group_id]["urls"].append({"path": row.path})
    
    url_groups = list(url_groups_data.values())
    
    return templates.TemplateResponse("application_detail.html", {
        "request": request, 
        "app": app,
        "url_groups": url_groups
    })

@app.get("/applications/{app_id}/edit-form", response_class=HTMLResponse)
async def applications_edit_form(
    request: Request, 
    app_id: int, 
    session: AsyncSession = Depends(get_async_session)
):
    """Get the application edit form."""
    app = await crud.get_application(session, app_id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    
    return templates.TemplateResponse("partials/applications_edit_form.html", {
        "request": request, 
        "app": app
    })

@app.put("/applications/{app_id}", response_class=HTMLResponse)
async def update_application_ui(
    request: Request, 
    app_id: int,
    name: str = Form(...), 
    host: str = Form(...), 
    description: str = Form(None),
    session: AsyncSession = Depends(get_async_session)
):
    """Update an application via UI."""
    try:
        await crud.update_application(session, app_id, name=name, host=host, description=description)
        
        # Check if we're on the detail page by looking for a specific header
        referer = request.headers.get("referer", "")
        if f"/applications/{app_id}" in referer:
            # We're on the detail page, return empty response
            return HTMLResponse("")
        else:
            # We're on the list page, return the updated list
            applications = await crud.get_all_applications_with_url_groups_count(session)
            return templates.TemplateResponse("partials/applications_list.html", {
                "request": request, 
                "applications": applications
            })
    except ValueError as e:
        # Return error message
        return HTMLResponse(f"<div class='text-red-600 p-4'>{str(e)}</div>")

@app.delete("/applications/{app_id}", response_class=HTMLResponse)
async def delete_application_ui(
    request: Request, 
    app_id: int, 
    session: AsyncSession = Depends(get_async_session)
):
    """Delete an application via UI."""
    success = await crud.delete_application(session, app_id)
    if not success:
        raise HTTPException(status_code=404, detail="Application not found")
    
    applications = await crud.get_all_applications_with_url_groups_count(session)
    return templates.TemplateResponse("partials/applications_list.html", {
        "request": request, 
        "applications": applications
    })

@app.get("/applications/{app_id}/url-groups/create-form", response_class=HTMLResponse)
async def url_groups_create_form_app(
    request: Request, 
    app_id: int, 
    session: AsyncSession = Depends(get_async_session)
):
    """Get the URL group creation form for an application."""
    app = await crud.get_application(session, app_id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    
    return templates.TemplateResponse("partials/url_groups_create_form.html", {
        "request": request, 
        "app": app
    })

@app.post("/applications/{app_id}/url-groups", response_class=HTMLResponse)
async def create_url_group_app(
    request: Request, 
    app_id: int,
    name: str = Form(...), 
    session: AsyncSession = Depends(get_async_session)
):
    """Create a new URL group for an application via UI."""
    try:
        await crud.create_url_group(session, name=name, app_id=app_id)
        app = await crud.get_application(session, app_id)
        
        # Get URL groups with their URLs in a single query
        url_groups_result = await session.execute(
            text("""
                SELECT 
                    ug.group_id, 
                    ug.name, 
                    ug.app_id,
                    ug.created_at,
                    ug.protected,
                    u.path
                FROM url_groups ug
                LEFT JOIN urls u ON ug.group_id = u.url_group_id
                WHERE ug.app_id = :app_id
                ORDER BY ug.name, u.path
            """),
            {"app_id": app_id}
        )
        
        # Group the results by URL group
        url_groups_data = {}
        for row in url_groups_result.fetchall():
            group_id = row.group_id
            if group_id not in url_groups_data:
                url_groups_data[group_id] = {
                    "group_id": group_id,
                    "name": row.name,
                    "app_id": row.app_id,
                    "created_at": row.created_at,
                    "protected": row.protected,
                    "urls": []
                }
            if row.path:  # Only add if path is not None
                url_groups_data[group_id]["urls"].append({"path": row.path})
        
        url_groups = list(url_groups_data.values())
        
        return templates.TemplateResponse("partials/url_groups_list.html", {
            "request": request, 
            "url_groups": url_groups,
            "app": app
        })
    except ValueError as e:
        # Return error message
        return HTMLResponse(f"<div class='text-red-600 p-4'>{str(e)}</div>")

@app.get("/url-groups/{group_id}/add-url-form", response_class=HTMLResponse)
async def url_groups_add_url_form(
    request: Request, 
    group_id: int, 
    session: AsyncSession = Depends(get_async_session)
):
    """Get the add URL form for a URL group."""
    group = await crud.get_url_group(session, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="URL group not found")
    
    return templates.TemplateResponse("partials/url_groups_add_url_form.html", {
        "request": request, 
        "group": group
    })

@app.post("/url-groups/{group_id}/add-url", response_class=HTMLResponse)
async def add_url_to_group_ui(
    request: Request, 
    group_id: int, 
    path: str = Form(...), 
    session: AsyncSession = Depends(get_async_session)
):
    """Add a URL to a group via UI."""
    try:
        # Validate input
        if not path or not path.strip():
            return HTMLResponse("<div class='text-red-600 p-4'>Error: URL path cannot be empty</div>")
        
        path = path.strip()
        
        # Check if URL already exists in this group
        existing_url = await session.execute(
            text("SELECT path FROM urls WHERE url_group_id = :group_id AND path = :path"),
            {"group_id": group_id, "path": path}
        )
        
        if existing_url.fetchone():
            return HTMLResponse("<div class='text-red-600 p-4'>Error: URL already exists in this group</div>")
        
        # Get the group to check if it exists and get app_id
        group = await crud.get_url_group(session, group_id)
        if not group:
            return HTMLResponse("<div class='text-red-600 p-4'>Error: URL group not found</div>")
        
        # Ensure URL exists or create
        db_url = await crud.get_url(session, path)
        if not db_url:
            await crud.create_url(session, path, group_id)
        else:
            await crud.add_url_to_group(session, group_id, path)
        
        # Return empty response for all contexts - let frontend handle page refresh
        return HTMLResponse("")
    except ValueError as e:
        return HTMLResponse(f"<div class='text-red-600 p-4'>Error: {str(e)}</div>")
    except Exception as e:
        return HTMLResponse(f"<div class='text-red-600 p-4'>Error: An unexpected error occurred while adding the URL</div>")

@app.delete("/url-groups/{group_id}/remove-url", response_class=HTMLResponse)
async def remove_url_from_group_ui(
    request: Request, 
    group_id: int, 
    path: str = Form(...), 
    session: AsyncSession = Depends(get_async_session)
):
    """Remove a URL from a group via UI."""
    try:
        await session.execute(delete(Url).where(Url.url_group_id == group_id, Url.path == path))
        await session.commit()
        
        # Return empty response for all contexts - let frontend handle page refresh
        return HTMLResponse("")
    except Exception as e:
        return HTMLResponse(f"<div class='text-red-600 p-4'>Error: {str(e)}</div>")

@app.delete("/url-groups/{group_id}", response_class=HTMLResponse)
async def delete_url_group_ui(
    request: Request, 
    group_id: int, 
    session: AsyncSession = Depends(get_async_session)
):
    """Delete a URL group via UI."""
    try:
        # Get the group to find its application
        group = await crud.get_url_group(session, group_id)
        if not group:
            raise HTTPException(status_code=404, detail="URL group not found")
        
        # Prevent deletion if protected
        if getattr(group, 'protected', False):
            return HTMLResponse("<div class='text-red-600 p-4'>Cannot delete protected URL group</div>")
        
        # Only allow deletion if there are no associations
        assoc_count = (await session.execute(
            text("SELECT COUNT(*) FROM user_group_url_group_associations WHERE url_group_id = :gid"), 
            {"gid": group_id}
        )).scalar()
        
        if assoc_count == 0:
            await session.execute(delete(UrlGroup).where(UrlGroup.group_id == group_id))
            await session.commit()
            
            if group.app_id:
                # Return updated URL groups list for the application
                app = await crud.get_application(session, group.app_id)
                
                # Get URL groups with their URLs in a single query
                url_groups_result = await session.execute(
                    text("""
                        SELECT 
                            ug.group_id, 
                            ug.name, 
                            ug.app_id,
                            ug.created_at,
                            ug.protected,
                            u.path
                        FROM url_groups ug
                        LEFT JOIN urls u ON ug.group_id = u.url_group_id
                        WHERE ug.app_id = :app_id
                        ORDER BY ug.name, u.path
                    """),
                    {"app_id": group.app_id}
                )
                
                # Group the results by URL group
                url_groups_data = {}
                for row in url_groups_result.fetchall():
                    g_group_id = row.group_id
                    if g_group_id not in url_groups_data:
                        url_groups_data[g_group_id] = {
                            "group_id": g_group_id,
                            "name": row.name,
                            "app_id": row.app_id,
                            "created_at": row.created_at,
                            "protected": row.protected,
                            "urls": []
                        }
                    if row.path:  # Only add if path is not None
                        url_groups_data[g_group_id]["urls"].append({"path": row.path})
                
                url_groups = list(url_groups_data.values())
                
                return templates.TemplateResponse("partials/url_groups_list.html", {
                    "request": request, 
                    "url_groups": url_groups,
                    "app": app
                })
            else:
                return HTMLResponse("<div class='text-green-600 p-4'>URL group deleted successfully</div>")
        else:
            return HTMLResponse("<div class='text-red-600 p-4'>Cannot delete URL group with existing associations</div>")
    except Exception as e:
        return HTMLResponse(f"<div class='text-red-600 p-4'>Error: {str(e)}</div>")

# Routers for API endpoints will be included here (e.g., from app.api.endpoints import ...)
# Example: app.include_router(user_group_router)
app.include_router(auth_router)
app.include_router(user_groups_router)
app.include_router(url_groups_router)
app.include_router(associations_router)
app.include_router(authorize_router)
app.include_router(applications_router)
