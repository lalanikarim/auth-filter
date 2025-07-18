from fastapi import APIRouter, Depends, Query, Cookie, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import get_async_session
from app import schemas, crud
from sqlalchemy import select
from app.models import UrlGroup, Url

router = APIRouter(tags=["authorize"])

@router.get("/api/authorize", response_model=schemas.AuthorizeResponse)
async def authorize(
    url: str = Query(..., alias="url"),
    x_auth_email: str = Cookie(None, alias="x-auth-email"),
    session: AsyncSession = Depends(get_async_session),
):
    # Check if URL is a web asset file that should bypass authentication/authorization
    if crud.is_web_asset(url):
        return schemas.AuthorizeResponse(allowed=True)
    
    # Check if URL is in the "Everyone" group (public access)
    everyone_query = (
        select(UrlGroup)
        .join(Url, UrlGroup.group_id == Url.url_group_id)
        .where(UrlGroup.name == "Everyone", Url.path == url)
    )
    result = await session.execute(everyone_query)
    if result.scalar_one_or_none():
        return schemas.AuthorizeResponse(allowed=True)
    
    # For all other URLs, require authentication
    if not x_auth_email:
        raise HTTPException(status_code=401, detail="Not authenticated: missing x-auth-email cookie")
    
    allowed = await crud.is_user_allowed(session, x_auth_email, url)
    return schemas.AuthorizeResponse(allowed=allowed) 