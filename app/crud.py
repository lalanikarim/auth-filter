from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import insert, update, delete, and_
from .models import User, UserGroup, UrlGroup, Url, user_group_members, user_group_url_group_associations
from typing import Optional
import os
import logging

# Set up logger
logger = logging.getLogger(__name__)

# Use sanitized logger to automatically mask sensitive information
from app.utils import SanitizedLogger, sanitize_email
logger = SanitizedLogger(logger)

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
        logger.debug("Empty URL path provided, not a web asset")
        return False
    
    # Remove query parameters and fragments
    clean_path = url_path.split('?')[0].split('#')[0]
    logger.debug(f"Checking if '{clean_path}' is a web asset")
    
    # Extract file extension from URL path
    path_parts = clean_path.split('.')
    if len(path_parts) < 2:
        logger.debug(f"No file extension found in '{clean_path}', not a web asset")
        return False
    
    file_extension = path_parts[-1].lower()
    allowed_extensions = [ext.strip().lower() for ext in ALLOWED_WEB_ASSET_EXTENSIONS]
    is_asset = file_extension in allowed_extensions
    
    if is_asset:
        logger.debug(f"'{clean_path}' is a web asset (extension: {file_extension})")
    else:
        logger.debug(f"'{clean_path}' is not a web asset (extension: {file_extension}, allowed: {allowed_extensions})")
    
    return is_asset

# User CRUD
async def create_user(session: AsyncSession, email: str) -> User:
    logger.info(f"Creating new user with email: {sanitize_email(email)}")
    user = User(email=email)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    logger.info(f"Created user with ID: {user.user_id}")
    return user

async def get_user(session: AsyncSession, email: str) -> Optional[User]:
    logger.debug(f"Looking up user with email: {sanitize_email(email)}")
    result = await session.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user:
        logger.debug(f"Found user with ID: {user.user_id}")
    else:
        logger.debug(f"User not found for email: {sanitize_email(email)}")
    return user

# UserGroup CRUD
async def create_user_group(session: AsyncSession, name: str) -> UserGroup:
    logger.info(f"Creating new user group: {name}")
    group = UserGroup(name=name)
    session.add(group)
    await session.commit()
    await session.refresh(group)
    logger.info(f"Created user group with ID: {group.group_id}")
    return group

async def get_user_group(session: AsyncSession, group_id: int) -> Optional[UserGroup]:
    logger.debug(f"Looking up user group with ID: {group_id}")
    result = await session.execute(select(UserGroup).where(UserGroup.group_id == group_id))
    group = result.scalar_one_or_none()
    if group:
        logger.debug(f"Found user group: {group.name}")
    else:
        logger.debug(f"User group not found for ID: {group_id}")
    return group

# Add user to user group
async def add_user_to_group(session: AsyncSession, group_id: int, email: str) -> bool:
    logger.info(f"Adding user '{sanitize_email(email)}' to group ID: {group_id}")
    # First get the user by email
    user = await get_user(session, email)
    if not user:
        logger.warning(f"User '{sanitize_email(email)}' not found, cannot add to group")
        return False
    
    stmt = insert(user_group_members).values(user_group_id=group_id, user_id=user.user_id).prefix_with("IGNORE")
    await session.execute(stmt)
    await session.commit()
    logger.info(f"Successfully added user '{sanitize_email(email)}' to group ID: {group_id}")
    return True

# UrlGroup CRUD
async def create_url_group(session: AsyncSession, name: str) -> UrlGroup:
    logger.info(f"Creating new URL group: {name}")
    group = UrlGroup(name=name)
    session.add(group)
    await session.commit()
    await session.refresh(group)
    logger.info(f"Created URL group with ID: {group.group_id}")
    return group

async def get_url_group(session: AsyncSession, group_id: int) -> Optional[UrlGroup]:
    logger.debug(f"Looking up URL group with ID: {group_id}")
    result = await session.execute(select(UrlGroup).where(UrlGroup.group_id == group_id))
    group = result.scalar_one_or_none()
    if group:
        logger.debug(f"Found URL group: {group.name}")
    else:
        logger.debug(f"URL group not found for ID: {group_id}")
    return group

# Add URL to URL group
async def add_url_to_group(session: AsyncSession, group_id: int, path: str) -> bool:
    logger.info(f"Adding URL '{path}' to group ID: {group_id}")
    url = Url(path=path, url_group_id=group_id)
    session.add(url)
    await session.commit()
    logger.info(f"Successfully added URL '{path}' to group ID: {group_id}")
    return True

# Link user group to url group
async def link_user_group_to_url_group(session: AsyncSession, user_group_id: int, url_group_id: int) -> bool:
    logger.info(f"Linking user group ID: {user_group_id} to URL group ID: {url_group_id}")
    stmt = insert(user_group_url_group_associations).values(user_group_id=user_group_id, url_group_id=url_group_id).prefix_with("IGNORE")
    await session.execute(stmt)
    await session.commit()
    logger.info(f"Successfully linked user group ID: {user_group_id} to URL group ID: {url_group_id}")
    return True

# Authorization check
async def is_user_allowed(session: AsyncSession, email: str, url_path: str) -> bool:
    logger.info(f"Checking authorization for user '{sanitize_email(email)}' accessing path '{url_path}'")
    
    # Check if URL is a web asset (should bypass auth)
    if is_web_asset(url_path):
        logger.info(f"URL '{url_path}' is a web asset, allowing access")
        return True
    
    # Check if URL is in 'Everyone' group (public)
    logger.debug("Checking if URL is in 'Everyone' group")
    q = (
        select(UrlGroup)
        .join(Url, UrlGroup.group_id == Url.url_group_id)
        .where(UrlGroup.name == "Everyone", UrlGroup.protected == 1, Url.path == url_path)
    )
    result = await session.execute(q)
    if result.scalar_one_or_none():
        logger.info(f"URL '{url_path}' is in 'Everyone' group, allowing access")
        return True

    # Check if URL is in 'Authenticated' group (any logged-in user)
    logger.debug("Checking if URL is in 'Authenticated' group")
    q = (
        select(UrlGroup)
        .join(Url, UrlGroup.group_id == Url.url_group_id)
        .where(UrlGroup.name == "Authenticated", UrlGroup.protected == 1, Url.path == url_path)
    )
    result = await session.execute(q)
    if result.scalar_one_or_none() and email:
        logger.info(f"URL '{url_path}' is in 'Authenticated' group and user '{sanitize_email(email)}' is logged in, allowing access")
        return True

    # Check if user is in Internal User Group (superuser)
    logger.debug("Checking if user is in 'Internal User Group'")
    q = (
        select(User)
        .join(user_group_members, User.user_id == user_group_members.c.user_id)
        .join(UserGroup, user_group_members.c.user_group_id == UserGroup.group_id)
        .where(User.email == email, UserGroup.name == "Internal User Group", UserGroup.protected == 1)
    )
    result = await session.execute(q)
    if result.scalar_one_or_none():
        logger.info(f"User '{sanitize_email(email)}' is in 'Internal User Group', allowing access to '{url_path}'")
        return True

    # Default: normal group-based check
    logger.debug("Performing normal group-based authorization check")
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
    user_found = result.scalar_one_or_none() is not None
    
    if user_found:
        logger.info(f"User '{sanitize_email(email)}' has access to '{url_path}' through group membership")
    else:
        logger.warning(f"User '{sanitize_email(email)}' denied access to '{url_path}' - no matching group permissions found")
    
    return user_found

async def get_url(session: AsyncSession, path: str) -> Optional[Url]:
    logger.debug(f"Looking up URL with path: {path}")
    result = await session.execute(select(Url).where(Url.path == path))
    url = result.scalar_one_or_none()
    if url:
        logger.debug(f"Found URL with ID: {url.url_id} in group ID: {url.url_group_id}")
    else:
        logger.debug(f"URL not found for path: {path}")
    return url

async def create_url(session: AsyncSession, path: str, url_group_id: int) -> Url:
    logger.info(f"Creating new URL '{path}' in group ID: {url_group_id}")
    url = Url(path=path, url_group_id=url_group_id)
    session.add(url)
    await session.commit()
    await session.refresh(url)
    logger.info(f"Created URL with ID: {url.url_id}")
    return url
