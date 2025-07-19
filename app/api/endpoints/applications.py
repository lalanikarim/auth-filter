from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import get_async_session
from app import schemas, crud
from typing import List

router = APIRouter(tags=["applications"])

@router.post("/api/applications", response_model=schemas.ApplicationRead)
async def create_application(
    application: schemas.ApplicationCreate,
    session: AsyncSession = Depends(get_async_session)
):
    """Create a new application."""
    # Check if application with this name or host already exists
    existing_app_by_name = await crud.get_application_by_name(session, application.name)
    if existing_app_by_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Application with name '{application.name}' already exists"
        )
    
    existing_app_by_host = await crud.get_application_by_host(session, application.host)
    if existing_app_by_host:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Application with host '{application.host}' already exists"
        )
    
    try:
        db_app = await crud.create_application(
            session, 
            name=application.name, 
            host=application.host, 
            description=application.description
        )
        return schemas.ApplicationRead(
            app_id=db_app.app_id,
            name=db_app.name,
            host=db_app.host,
            description=db_app.description,
            created_at=db_app.created_at
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("/api/applications", response_model=List[schemas.ApplicationRead])
async def list_applications(session: AsyncSession = Depends(get_async_session)):
    """List all applications."""
    applications = await crud.get_all_applications(session)
    return [
        schemas.ApplicationRead(
            app_id=app.app_id,
            name=app.name,
            host=app.host,
            description=app.description,
            created_at=app.created_at
        )
        for app in applications
    ]

@router.get("/api/applications/{app_id}", response_model=schemas.ApplicationRead)
async def get_application(
    app_id: int,
    session: AsyncSession = Depends(get_async_session)
):
    """Get a specific application by ID."""
    app = await crud.get_application(session, app_id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    
    return schemas.ApplicationRead(
        app_id=app.app_id,
        name=app.name,
        host=app.host,
        description=app.description,
        created_at=app.created_at
    )

@router.put("/api/applications/{app_id}", response_model=schemas.ApplicationRead)
async def update_application(
    app_id: int,
    application: schemas.ApplicationCreate,
    session: AsyncSession = Depends(get_async_session)
):
    """Update an application."""
    # Check if application exists
    existing_app = await crud.get_application(session, app_id)
    if not existing_app:
        raise HTTPException(status_code=404, detail="Application not found")
    
    # Check if name or host conflicts with other applications
    if application.name != existing_app.name:
        conflict_app = await crud.get_application_by_name(session, application.name)
        if conflict_app and conflict_app.app_id != app_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Application with name '{application.name}' already exists"
            )
    
    if application.host != existing_app.host:
        conflict_app = await crud.get_application_by_host(session, application.host)
        if conflict_app and conflict_app.app_id != app_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Application with host '{application.host}' already exists"
            )
    
    try:
        updated_app = await crud.update_application(
            session, 
            app_id, 
            name=application.name,
            host=application.host,
            description=application.description
        )
        return schemas.ApplicationRead(
            app_id=updated_app.app_id,
            name=updated_app.name,
            host=updated_app.host,
            description=updated_app.description,
            created_at=updated_app.created_at
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.delete("/api/applications/{app_id}")
async def delete_application(
    app_id: int,
    session: AsyncSession = Depends(get_async_session)
):
    """Delete an application."""
    success = await crud.delete_application(session, app_id)
    if not success:
        raise HTTPException(status_code=404, detail="Application not found")
    return {"message": "Application deleted successfully"}

@router.get("/api/applications/{app_id}/url-groups", response_model=List[schemas.UrlGroupRead])
async def get_application_url_groups(app_id: int, session: AsyncSession = Depends(get_async_session)):
    """Get all URL groups for a specific application."""
    # Verify application exists
    application = await crud.get_application(session, app_id)
    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
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