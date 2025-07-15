from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import get_async_session
from app import schemas, crud

router = APIRouter(tags=["associations"])

@router.post("/api/associations", response_model=schemas.SuccessResponse)
async def link_user_group_to_url_group(
    assoc: schemas.UserGroupUrlGroupAssociationCreate,
    session: AsyncSession = Depends(get_async_session),
):
    # Ensure user group exists
    user_group = await crud.get_user_group(session, assoc.user_group_id)
    if not user_group:
        raise HTTPException(status_code=404, detail="User group not found")
    # Ensure url group exists
    url_group = await crud.get_url_group(session, assoc.url_group_id)
    if not url_group:
        raise HTTPException(status_code=404, detail="URL group not found")
    await crud.link_user_group_to_url_group(session, assoc.user_group_id, assoc.url_group_id)
    return schemas.SuccessResponse(success=True) 