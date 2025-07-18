from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import insert, update, delete, and_
from .models import User, UserGroup, UrlGroup, Url, user_group_members, user_group_url_group_associations
from typing import Optional
import os

# Web asset file extensions that should bypass authentication/authorization checks
ALLOWED_WEB_ASSET_EXTENSIONS = os.getenv("ALLOWED_WEB_ASSET_EXTENSIONS", "css,js,png,jpg,jpeg,gif,svg,ico,woff,woff2,ttf,eot,map").split(",")

def is_web_asset(url_path: str) -> bool:
    """
    Check if the URL path is a web asset file that should bypass authentication/authorization checks.
    
    Args:
        url_path: The URL path to check
        
    Returns:
        True if the URL path is a web asset file, False otherwise
    """
    if not url_path:
        return False
    
    # Remove query parameters and fragments
    clean_path = url_path.split('?')[0].split('#')[0]
    
    # Extract file extension from URL path
    path_parts = clean_path.split('.')
    if len(path_parts) < 2:
        return False
    
    file_extension = path_parts[-1].lower()
    return file_extension in [ext.strip().lower() for ext in ALLOWED_WEB_ASSET_EXTENSIONS]

# User CRUD
async def create_user(session: AsyncSession, email: str) -> User:
    user = User(email=email)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user

async def get_user(session: AsyncSession, email: str) -> Optional[User]:
    result = await session.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()

# UserGroup CRUD
async def create_user_group(session: AsyncSession, name: str) -> UserGroup:
    group = UserGroup(name=name)
    session.add(group)
    await session.commit()
    await session.refresh(group)
    return group

async def get_user_group(session: AsyncSession, group_id: int) -> Optional[UserGroup]:
    result = await session.execute(select(UserGroup).where(UserGroup.group_id == group_id))
    return result.scalar_one_or_none()

# Add user to user group
async def add_user_to_group(session: AsyncSession, group_id: int, email: str) -> bool:
    # First get the user by email
    user = await get_user(session, email)
    if not user:
        return False
    
    stmt = insert(user_group_members).values(user_group_id=group_id, user_id=user.user_id).prefix_with("IGNORE")
    await session.execute(stmt)
    await session.commit()
    return True

# UrlGroup CRUD
async def create_url_group(session: AsyncSession, name: str) -> UrlGroup:
    group = UrlGroup(name=name)
    session.add(group)
    await session.commit()
    await session.refresh(group)
    return group

async def get_url_group(session: AsyncSession, group_id: int) -> Optional[UrlGroup]:
    result = await session.execute(select(UrlGroup).where(UrlGroup.group_id == group_id))
    return result.scalar_one_or_none()

# Add URL to URL group
async def add_url_to_group(session: AsyncSession, group_id: int, path: str) -> bool:
    url = Url(path=path, url_group_id=group_id)
    session.add(url)
    await session.commit()
    return True

# Link user group to url group
async def link_user_group_to_url_group(session: AsyncSession, user_group_id: int, url_group_id: int) -> bool:
    stmt = insert(user_group_url_group_associations).values(user_group_id=user_group_id, url_group_id=url_group_id).prefix_with("IGNORE")
    await session.execute(stmt)
    await session.commit()
    return True

# Authorization check
async def is_user_allowed(session: AsyncSession, email: str, url_path: str) -> bool:
    # Check if URL is in 'Everyone' group (public)
    q = (
        select(UrlGroup)
        .join(Url, UrlGroup.group_id == Url.url_group_id)
        .where(UrlGroup.name == "Everyone", UrlGroup.protected == 1, Url.path == url_path)
    )
    result = await session.execute(q)
    if result.scalar_one_or_none():
        return True

    # Check if URL is in 'Authenticated' group (any logged-in user)
    q = (
        select(UrlGroup)
        .join(Url, UrlGroup.group_id == Url.url_group_id)
        .where(UrlGroup.name == "Authenticated", UrlGroup.protected == 1, Url.path == url_path)
    )
    result = await session.execute(q)
    if result.scalar_one_or_none() and email:
        return True

    # Check if user is in Internal User Group (superuser)
    q = (
        select(User)
        .join(user_group_members, User.user_id == user_group_members.c.user_id)
        .join(UserGroup, user_group_members.c.user_group_id == UserGroup.group_id)
        .where(User.email == email, UserGroup.name == "Internal User Group", UserGroup.protected == 1)
    )
    result = await session.execute(q)
    if result.scalar_one_or_none():
        return True

    # Default: normal group-based check
    q = (
        select(User)
        .join(user_group_members, User.user_id == user_group_members.c.user_id)
        .join(UserGroup, user_group_members.c.user_group_id == UserGroup.group_id)
        .join(user_group_url_group_associations, UserGroup.group_id == user_group_url_group_associations.c.user_group_id)
        .join(UrlGroup, user_group_url_group_associations.c.url_group_id == UrlGroup.group_id)
        .join(Url, UrlGroup.group_id == Url.url_group_id)
        .where(and_(User.email == email, Url.path == url_path))
    )
    result = await session.execute(q)
    return result.scalar_one_or_none() is not None

async def get_url(session: AsyncSession, path: str) -> Optional[Url]:
    result = await session.execute(select(Url).where(Url.path == path))
    return result.scalar_one_or_none()

async def create_url(session: AsyncSession, path: str, url_group_id: int) -> Url:
    url = Url(path=path, url_group_id=url_group_id)
    session.add(url)
    await session.commit()
    await session.refresh(url)
    return url
