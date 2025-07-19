from fastapi import APIRouter, Depends, Query, Cookie, HTTPException, Response
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
    response: Response = None,
):
    # Use the new full URL authorization function
    allowed = await crud.is_user_allowed_full_url(session, x_auth_email, url)
    
    if allowed:
        response.status_code = 200
    else:
        response.status_code = 403
    return schemas.AuthorizeResponse(allowed=allowed) 