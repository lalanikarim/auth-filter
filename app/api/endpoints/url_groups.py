from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import get_async_session
from app import schemas, crud
from typing import List, Optional

router = APIRouter(prefix="/api/url-groups", tags=["url-groups"])

@router.post("", response_model=schemas.UrlGroupRead)
async def create_url_group(
    group: schemas.UrlGroupCreate,
    session: AsyncSession = Depends(get_async_session),
):
    # If app_id is provided, verify the application exists
    if group.app_id:
        app = await crud.get_application(session, group.app_id)
        if not app:
            raise HTTPException(
                status_code=404, 
                detail=f"Application with ID {group.app_id} not found"
            )
    
    try:
        db_group = await crud.create_url_group(session, name=group.name, app_id=group.app_id)
        return schemas.UrlGroupRead(
            group_id=db_group.group_id,
            name=db_group.name,
            created_at=db_group.created_at,
            app_id=db_group.app_id,
            application=None,
            urls=None
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

@router.get("", response_model=List[schemas.UrlGroupRead])
async def list_url_groups(
    app_id: Optional[int] = Query(None, description="Filter by application ID"),
    session: AsyncSession = Depends(get_async_session),
):
    """List URL groups, optionally filtered by application."""
    if app_id:
        # Verify application exists if app_id is provided
        app = await crud.get_application(session, app_id)
        if not app:
            raise HTTPException(
                status_code=404, 
                detail=f"Application with ID {app_id} not found"
            )
    
    url_groups = await crud.list_url_groups_by_application(session, app_id)
    return [
        schemas.UrlGroupRead(
            group_id=group.group_id,
            name=group.name,
            created_at=group.created_at,
            app_id=group.app_id,
            application=None,
            urls=None
        )
        for group in url_groups
    ]

@router.get("/{group_id}", response_model=schemas.UrlGroupRead)
async def get_url_group(
    group_id: int = Path(..., description="URL group ID"),
    session: AsyncSession = Depends(get_async_session),
):
    """Get a specific URL group by ID."""
    db_group = await crud.get_url_group(session, group_id)
    if not db_group:
        raise HTTPException(status_code=404, detail="URL group not found")
    
    return schemas.UrlGroupRead(
        group_id=db_group.group_id,
        name=db_group.name,
        created_at=db_group.created_at,
        app_id=db_group.app_id,
        application=None,
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