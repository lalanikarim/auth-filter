from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import get_async_session
from app import schemas, crud

router = APIRouter(tags=["authorize"])

@router.post("/api/authorize", response_model=schemas.AuthorizeResponse)
async def authorize(
    req: schemas.AuthorizeRequest,
    session: AsyncSession = Depends(get_async_session),
):
    allowed = await crud.is_user_allowed(session, req.email, req.url_path)
    return schemas.AuthorizeResponse(allowed=allowed) 