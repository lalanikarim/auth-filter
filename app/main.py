from fastapi import FastAPI, Request
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

# Routers for API endpoints will be included here (e.g., from app.api.endpoints import ...)
# Example: app.include_router(user_group_router)
app.include_router(auth_router)
app.include_router(user_groups_router)
app.include_router(url_groups_router)
app.include_router(associations_router)
app.include_router(authorize_router)
