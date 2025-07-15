from fastapi import APIRouter, Depends, Query, Cookie, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import get_async_session
from app import schemas, crud

router = APIRouter(tags=["authorize"])

@router.get("/api/authorize", response_model=schemas.AuthorizeResponse)
async def authorize(
    url: str = Query(..., alias="url"),
    x_auth_email: str = Cookie(None, alias="x-auth-email"),
    session: AsyncSession = Depends(get_async_session),
):
    if not x_auth_email:
        raise HTTPException(status_code=401, detail="Not authenticated: missing x-auth-email cookie")
    allowed = await crud.is_user_allowed(session, x_auth_email, url)
    return schemas.AuthorizeResponse(allowed=allowed) 