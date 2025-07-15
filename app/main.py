from fastapi import FastAPI, Request, Form, Depends, status, Body, Cookie, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from .db import engine, Base
import asyncio
from app.api.endpoints import auth_router
from app.api.endpoints import user_groups_router
from app.api.endpoints import url_groups_router
from app.api.endpoints import associations_router
from app.api.endpoints import authorize_router
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
from dotenv import load_dotenv
import requests
from urllib.parse import urlencode, quote, unquote
from jose import jwt, JWTError
import json
import time

load_dotenv()

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

@app.on_event("startup")
async def on_startup():
    # Auto-create tables in dev (SQLite). In prod, use Alembic for migrations.
    if engine.url.drivername.startswith("sqlite"):
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse("base.html", {"request": request})

@app.get("/user-groups")
async def user_groups(request: Request, session: AsyncSession = Depends(get_async_session)):
    selected = request.query_params.get("selected")
    result = await session.execute(text("SELECT group_id, name FROM user_groups ORDER BY group_id"))
    groups = result.fetchall()
    # Fetch users in each group
    user_map = defaultdict(list)
    user_rows = await session.execute(text("SELECT user_group_id, user_email FROM user_group_members ORDER BY user_group_id, user_email"))
    for row in user_rows:
        user_map[row.user_group_id].append(row.user_email)
    # Fetch associations for delete button logic and for url group lookup
    assoc_rows = await session.execute(text('''
        SELECT a.user_group_id, a.url_group_id
        FROM user_group_url_group_associations a
    '''))
    associations = assoc_rows.fetchall()
    associated_user_group_ids = set(row.user_group_id for row in associations)
    # Fetch all url groups
    url_group_rows = await session.execute(text("SELECT group_id, name FROM url_groups ORDER BY group_id"))
    url_groups = url_group_rows.fetchall()
    # Prepare selected group data
    selected_group = None
    selected_group_users = []
    selected_group_url_group_ids = []
    selected_group_url_groups = []
    if selected:
        try:
            selected_id = int(selected)
            selected_group = next((g for g in groups if g.group_id == selected_id), None)
            if selected_group:
                selected_group_users = user_map.get(selected_id, [])
                selected_group_url_group_ids = [a.url_group_id for a in associations if a.user_group_id == selected_id]
                selected_group_url_groups = [g for g in url_groups if g.group_id in selected_group_url_group_ids]
        except Exception:
            selected_group = None
    return templates.TemplateResponse("user_groups.html", {
        "request": request,
        "groups": groups,
        "users_in_group": user_map,
        "associations": associations,
        "associated_user_group_ids": associated_user_group_ids,
        "url_groups": url_groups,
        "selected_group": selected_group,
        "selected_group_users": selected_group_users,
        "selected_group_url_groups": selected_group_url_groups,
        "selected": selected
    })

@app.post("/user-groups")
async def create_user_group(request: Request, name: str = Form(...), session: AsyncSession = Depends(get_async_session)):
    from sqlalchemy.exc import IntegrityError
    try:
        await crud.create_user_group(session, name)
    except IntegrityError:
        await session.rollback()
        # Optionally, add flash message logic here
    return RedirectResponse(url="/user-groups", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/user-groups/{group_id}/add-user")
async def add_user_to_group(request: Request, group_id: int, email: str = Form(...), session: AsyncSession = Depends(get_async_session)):
    # Ensure user exists or create
    db_user = await crud.get_user(session, email)
    if not db_user:
        await crud.create_user(session, email)
    await crud.add_user_to_group(session, group_id, email)
    return RedirectResponse(url=f"/user-groups?selected={group_id}", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/user-groups/{group_id}/remove-user")
async def remove_user_from_group(request: Request, group_id: int, email: str = Form(...), session: AsyncSession = Depends(get_async_session)):
    await session.execute(delete(user_group_members).where(user_group_members.c.user_group_id == group_id, user_group_members.c.user_email == email))
    await session.commit()
    return RedirectResponse(url=f"/user-groups?selected={group_id}", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/user-groups/{group_id}/delete")
async def delete_user_group(request: Request, group_id: int, session: AsyncSession = Depends(get_async_session)):
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
        await crud.create_url_group(session, name)
    except IntegrityError:
        await session.rollback()
        # Optionally, add flash message logic here
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
    # Only allow deletion if there are no associations
    assoc_count = (await session.execute(text("SELECT COUNT(*) FROM user_group_url_group_associations WHERE url_group_id = :gid"), {"gid": group_id})).scalar()
    if assoc_count == 0:
        await session.execute(delete(UrlGroup).where(UrlGroup.group_id == group_id))
        await session.commit()
    return RedirectResponse(url="/url-groups", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/associations")
async def associations(request: Request, session: AsyncSession = Depends(get_async_session)):
    # Get all associations with group names
    result = await session.execute(text('''
        SELECT a.user_group_id, ug.name as user_group_name, a.url_group_id, ugg.name as url_group_name
        FROM user_group_url_group_associations a
        JOIN user_groups ug ON a.user_group_id = ug.group_id
        JOIN url_groups ugg ON a.url_group_id = ugg.group_id
        ORDER BY a.user_group_id, a.url_group_id
    '''))
    associations = result.fetchall()
    user_groups = (await session.execute(text("SELECT group_id, name FROM user_groups ORDER BY name"))).fetchall()
    url_groups = (await session.execute(text("SELECT group_id, name FROM url_groups ORDER BY name"))).fetchall()
    return templates.TemplateResponse("associations.html", {"request": request, "associations": associations, "user_groups": user_groups, "url_groups": url_groups})

@app.post("/associations")
async def create_association(request: Request, user_group_id: int = Form(...), url_group_id: int = Form(...), session: AsyncSession = Depends(get_async_session)):
    await crud.link_user_group_to_url_group(session, user_group_id, url_group_id)
    return RedirectResponse(url="/associations", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/associations/remove")
async def remove_association(request: Request, user_group_id: int = Form(...), url_group_id: int = Form(...), session: AsyncSession = Depends(get_async_session)):
    from app.models import user_group_url_group_associations
    await session.execute(
        delete(user_group_url_group_associations).where(
            user_group_url_group_associations.c.user_group_id == user_group_id,
            user_group_url_group_associations.c.url_group_id == url_group_id
        )
    )
    await session.commit()
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

# Protect /authorize UI
@app.get("/authorize", response_class=HTMLResponse)
async def authorize_page(request: Request, user=Depends(get_current_user_from_cookie)):
    next_path = request.query_params.get("next", None)
    url_path = request.query_params.get("url_path", "")
    email = request.query_params.get("email", "")
    return templates.TemplateResponse("authorize.html", {"request": request, "allowed": None, "user": user, "next": next_path, "url_path": url_path, "email": email})

@app.post("/authorize", response_class=HTMLResponse)
async def authorize_check(request: Request, email: str = Form(None), url_path: str = Form(None), session: AsyncSession = Depends(get_async_session), user=Depends(get_current_user_from_cookie)):
    # Fallback to query string if not present in form
    if not url_path:
        url_path = request.query_params.get("url_path", "")
    if not email:
        email = request.query_params.get("email", "")
    from app.crud import is_user_allowed
    allowed = await is_user_allowed(session, email, url_path)
    return templates.TemplateResponse("authorize.html", {"request": request, "allowed": allowed, "email": email, "url_path": url_path, "user": user})

@app.get("/auth/login")
def auth_login(request: Request):
    next_path = request.query_params.get("next", "/")
    # Only allow relative paths for security
    if not next_path.startswith("/"):
        next_path = "/"
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
    return RedirectResponse(url)

@app.get("/auth/callback")
def auth_callback(request: Request):
    code = request.query_params.get("code")
    state = request.query_params.get("state", "%2F")
    next_path = unquote(unquote(state))
    if not next_path.startswith("/"):
        next_path = "/"
    if not code:
        return HTMLResponse("Missing code", status_code=400)
    data = {
        "code": code,
        "client_id": OAUTH2_CLIENT_ID,
        "client_secret": OAUTH2_CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
    }
    token_resp = requests.post(OAUTH2_TOKEN_URL, data=data)
    if not token_resp.ok:
        print("OAuth2 token exchange error:", token_resp.text)
        return HTMLResponse(f"Token exchange failed: {token_resp.text}", status_code=400)
    token_data = token_resp.json()
    id_token = token_data.get("id_token")
    if not id_token:
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
            return HTMLResponse("No email in token", status_code=400)
    except Exception as e:
        return HTMLResponse(f"Token decode error: {str(e)}", status_code=400)
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
        max_age=3600
    )
    response.set_cookie(
        "x-auth-email",
        email,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        max_age=3600
    )
    return response

@app.get("/logout")
def logout():
    response = RedirectResponse(url="/")
    response.delete_cookie(COOKIE_NAME)
    return response

# Routers for API endpoints will be included here (e.g., from app.api.endpoints import ...)
# Example: app.include_router(user_group_router)
app.include_router(auth_router)
app.include_router(user_groups_router)
app.include_router(url_groups_router)
app.include_router(associations_router)
app.include_router(authorize_router)
