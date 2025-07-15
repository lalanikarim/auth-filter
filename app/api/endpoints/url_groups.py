from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import get_async_session
from app import schemas, crud

router = APIRouter(prefix="/api/url-groups", tags=["url-groups"])

@router.post("", response_model=schemas.UrlGroupRead)
async def create_url_group(
    group: schemas.UrlGroupCreate,
    session: AsyncSession = Depends(get_async_session),
):
    db_group = await crud.create_url_group(session, name=group.name)
    # Patch: avoid lazy loading urls
    return schemas.UrlGroupRead(
        group_id=db_group.group_id,
        name=db_group.name,
        created_at=db_group.created_at,
        urls=None
    )

@router.post("/{group_id}/urls", response_model=schemas.SuccessResponse)
async def add_url_to_group(
    group_id: int = Path(..., description="URL group ID"),
    url: schemas.UrlCreate = None,
    session: AsyncSession = Depends(get_async_session),
):
    # Ensure group exists
    db_group = await crud.get_url_group(session, group_id)
    if not db_group:
        raise HTTPException(status_code=404, detail="URL group not found")
    await crud.add_url_to_group(session, group_id, url.path)
    return schemas.SuccessResponse(success=True) 