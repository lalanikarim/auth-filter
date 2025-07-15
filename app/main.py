from fastapi import FastAPI, Request, Form, Depends, status, Body
from fastapi.responses import RedirectResponse, HTMLResponse
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
    result = await session.execute(text("SELECT group_id, name FROM user_groups ORDER BY group_id"))
    groups = result.fetchall()
    # Fetch users in each group
    user_map = defaultdict(list)
    user_rows = await session.execute(text("SELECT user_group_id, user_email FROM user_group_members ORDER BY user_group_id, user_email"))
    for row in user_rows:
        user_map[row.user_group_id].append(row.user_email)
    # Fetch associations for delete button logic
    assoc_rows = await session.execute(text('''
        SELECT a.user_group_id, a.url_group_id
        FROM user_group_url_group_associations a
    '''))
    associations = assoc_rows.fetchall()
    associated_user_group_ids = set(row.user_group_id for row in associations)
    return templates.TemplateResponse("user_groups.html", {"request": request, "groups": groups, "users_in_group": user_map, "associations": associations, "associated_user_group_ids": associated_user_group_ids})

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
    return RedirectResponse(url="/user-groups", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/user-groups/{group_id}/remove-user")
async def remove_user_from_group(request: Request, group_id: int, email: str = Form(...), session: AsyncSession = Depends(get_async_session)):
    await session.execute(delete(user_group_members).where(user_group_members.c.user_group_id == group_id, user_group_members.c.user_email == email))
    await session.commit()
    return RedirectResponse(url="/user-groups", status_code=status.HTTP_303_SEE_OTHER)

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
    result = await session.execute(text("SELECT group_id, name FROM url_groups ORDER BY group_id"))
    groups = result.fetchall()
    # Fetch urls in each group
    url_map = defaultdict(list)
    url_rows = await session.execute(text("SELECT url_group_id, path FROM urls ORDER BY url_group_id, path"))
    for row in url_rows:
        url_map[row.url_group_id].append(row.path)
    # Fetch associations for delete button logic
    assoc_rows = await session.execute(text('''
        SELECT a.user_group_id, a.url_group_id
        FROM user_group_url_group_associations a
    '''))
    associations = assoc_rows.fetchall()
    associated_url_group_ids = set(row.url_group_id for row in associations)
    return templates.TemplateResponse("url_groups.html", {"request": request, "groups": groups, "urls_in_group": url_map, "associations": associations, "associated_url_group_ids": associated_url_group_ids})

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
    return RedirectResponse(url="/url-groups", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/url-groups/{group_id}/remove-url")
async def remove_url_from_group(request: Request, group_id: int, path: str = Form(...), session: AsyncSession = Depends(get_async_session)):
    await session.execute(delete(Url).where(Url.url_group_id == group_id, Url.path == path))
    await session.commit()
    return RedirectResponse(url="/url-groups", status_code=status.HTTP_303_SEE_OTHER)

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

@app.get("/authorize", response_class=HTMLResponse)
async def authorize_page(request: Request):
    return templates.TemplateResponse("authorize.html", {"request": request, "allowed": None})

@app.post("/authorize", response_class=HTMLResponse)
async def authorize_check(request: Request, email: str = Form(...), url_path: str = Form(...), session: AsyncSession = Depends(get_async_session)):
    from app.crud import is_user_allowed
    allowed = await is_user_allowed(session, email, url_path)
    return templates.TemplateResponse("authorize.html", {"request": request, "allowed": allowed, "email": email, "url_path": url_path})

@app.post("/api/authorize")
async def api_authorize(
    email: str = Form(None),
    url_path: str = Form(None),
    session: AsyncSession = Depends(get_async_session),
    body: dict = Body(None)
):
    # Support both form and JSON
    if body:
        email = body.get("email", email)
        url_path = body.get("url_path", url_path)
    from app.crud import is_user_allowed
    allowed = await is_user_allowed(session, email, url_path)
    if allowed:
        return HTMLResponse(status_code=200)
    else:
        return HTMLResponse(status_code=403)

# Routers for API endpoints will be included here (e.g., from app.api.endpoints import ...)
# Example: app.include_router(user_group_router)
app.include_router(auth_router)
app.include_router(user_groups_router)
app.include_router(url_groups_router)
app.include_router(associations_router)
app.include_router(authorize_router)
