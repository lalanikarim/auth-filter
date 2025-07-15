from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import get_async_session
from app import schemas, crud

router = APIRouter(prefix="/api/user-groups", tags=["user-groups"])

@router.post("", response_model=schemas.UserGroupRead)
async def create_user_group(
    group: schemas.UserGroupCreate,
    session: AsyncSession = Depends(get_async_session),
):
    db_group = await crud.create_user_group(session, name=group.name)
    # Patch: avoid lazy loading users
    return schemas.UserGroupRead(
        group_id=db_group.group_id,
        name=db_group.name,
        created_at=db_group.created_at,
        users=None
    )

@router.post("/{group_id}/users", response_model=schemas.SuccessResponse)
async def add_user_to_group(
    group_id: int = Path(..., description="User group ID"),
    user: schemas.UserCreate = None,
    session: AsyncSession = Depends(get_async_session),
):
    # Ensure group exists
    db_group = await crud.get_user_group(session, group_id)
    if not db_group:
        raise HTTPException(status_code=404, detail="User group not found")
    # Ensure user exists or create
    db_user = await crud.get_user(session, user.email)
    if not db_user:
        db_user = await crud.create_user(session, user.email)
    await crud.add_user_to_group(session, group_id, user.email)
    return schemas.SuccessResponse(success=True) 