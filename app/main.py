from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
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

@app.get("/user-groups", response_class=HTMLResponse)
async def user_groups_page(request: Request):
    return templates.TemplateResponse("user_groups.html", {"request": request})

@app.get("/url-groups", response_class=HTMLResponse)
async def url_groups_page(request: Request):
    return templates.TemplateResponse("url_groups.html", {"request": request})

@app.get("/associations", response_class=HTMLResponse)
async def associations_page(request: Request):
    return templates.TemplateResponse("associations.html", {"request": request})

@app.get("/authorize", response_class=HTMLResponse)
async def authorize_page(request: Request):
    return templates.TemplateResponse("authorize.html", {"request": request})

@app.get("/htmx/user-groups/list", response_class=HTMLResponse)
async def htmx_user_groups_list(session: AsyncSession = Depends(get_async_session)):
    # List all user groups
    result = await session.execute("SELECT group_id, name FROM user_groups ORDER BY group_id")
    groups = result.fetchall()
    return templates.TemplateResponse("partials/user_groups_list.html", {"groups": groups})

@app.get("/htmx/user-groups/create-form", response_class=HTMLResponse)
async def htmx_user_groups_create_form(request: Request):
    return templates.TemplateResponse("partials/user_groups_create_form.html", {"request": request})

@app.post("/htmx/user-groups/create", response_class=HTMLResponse)
async def htmx_user_groups_create(
    name: str = Form(...),
    session: AsyncSession = Depends(get_async_session),
):
    await crud.create_user_group(session, name)
    # Return updated list
    result = await session.execute("SELECT group_id, name FROM user_groups ORDER BY group_id")
    groups = result.fetchall()
    return templates.TemplateResponse("partials/user_groups_list.html", {"groups": groups})

@app.get("/htmx/user-groups/{group_id}/add-user-form", response_class=HTMLResponse)
async def htmx_user_groups_add_user_form(request: Request, group_id: int):
    return templates.TemplateResponse("partials/user_groups_add_user_form.html", {"request": request, "group_id": group_id})

@app.post("/htmx/user-groups/{group_id}/add-user", response_class=HTMLResponse)
async def htmx_user_groups_add_user(
    group_id: int,
    email: str = Form(...),
    session: AsyncSession = Depends(get_async_session),
):
    # Ensure user exists or create
    db_user = await crud.get_user(session, email)
    if not db_user:
        await crud.create_user(session, email)
    await crud.add_user_to_group(session, group_id, email)
    # Return updated list
    result = await session.execute("SELECT group_id, name FROM user_groups ORDER BY group_id")
    groups = result.fetchall()
    return templates.TemplateResponse("partials/user_groups_list.html", {"groups": groups})

# Routers for API endpoints will be included here (e.g., from app.api.endpoints import ...)
# Example: app.include_router(user_group_router)
app.include_router(auth_router)
app.include_router(user_groups_router)
app.include_router(url_groups_router)
app.include_router(associations_router)
app.include_router(authorize_router)
