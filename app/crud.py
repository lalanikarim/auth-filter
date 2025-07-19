from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import insert, update, delete, and_
from .models import User, UserGroup, UrlGroup, Url, Application, user_group_members, user_group_url_group_associations
from typing import Optional, List
import os
import logging
from sqlalchemy.exc import IntegrityError
from urllib.parse import urlparse
import re

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

def parse_full_url(full_url: str) -> tuple[str, str, str]:
    """
    Parse a full URL and return (scheme, host, path).
    Handles both full URLs (https://example.com/path) and relative paths (/path).
    """
    if full_url.startswith(('http://', 'https://')):
        parsed = urlparse(full_url)
        return parsed.scheme, parsed.netloc, parsed.path
    else:
        # Assume it's a relative path
        return '', '', full_url

async def is_user_allowed_full_url(session: AsyncSession, email: str, full_url: str) -> bool:
    """
    Check if user is allowed to access a full URL (including scheme and host).
    This function handles application-based authorization by matching the host.
    """
    logger.info(f"Checking authorization for user '{sanitize_email(email)}' accessing URL '{full_url}'")
    
    scheme, host, path = parse_full_url(full_url)
    
    # Check if URL is a web asset (should bypass auth)
    if is_web_asset(path):
        logger.info(f"URL '{full_url}' is a web asset, allowing access")
        return True
    
    # If we have a host, check if it matches any application
    if host:
        app = await get_application_by_host(session, host)
        if app:
            logger.info(f"Found application '{app.name}' for host '{host}'")
            # For application URLs, we need to check if the path is allowed
            return await is_user_allowed_for_application(session, email, path, app.app_id)
        else:
            logger.warning(f"No application found for host '{host}', denying access")
            return False
    
    # If no host (relative path), fall back to the original logic
    logger.info(f"No host in URL '{full_url}', using path-based authorization")
    return await is_user_allowed(session, email, path)

async def is_user_allowed_for_application(session: AsyncSession, email: str, path: str, app_id: int) -> bool:
    """
    Check if user is allowed to access a path within a specific application.
    This function only checks URL groups that belong to the specified application.
    """
    logger.info(f"Checking application-specific authorization for user '{sanitize_email(email)}' accessing path '{path}' in app ID {app_id}")
    
    # Check if URL is in 'Everyone' group for this application
    logger.debug("Checking if URL is in 'Everyone' group for this application")
    q = (
        select(UrlGroup)
        .join(Url, UrlGroup.group_id == Url.url_group_id)
        .where(
            UrlGroup.name == "Everyone", 
            UrlGroup.protected == 1, 
            UrlGroup.app_id == app_id,
            Url.path == path
        )
    )
    result = await session.execute(q)
    if result.scalar_one_or_none():
        logger.info(f"URL '{path}' is in 'Everyone' group for app {app_id}, allowing access")
        return True

    # Check if URL is in 'Authenticated' group for this application
    logger.debug("Checking if URL is in 'Authenticated' group for this application")
    q = (
        select(UrlGroup)
        .join(Url, UrlGroup.group_id == Url.url_group_id)
        .where(
            UrlGroup.name == "Authenticated", 
            UrlGroup.protected == 1, 
            UrlGroup.app_id == app_id,
            Url.path == path
        )
    )
    result = await session.execute(q)
    if result.scalar_one_or_none() and email:
        logger.info(f"URL '{path}' is in 'Authenticated' group for app {app_id} and user '{sanitize_email(email)}' is logged in, allowing access")
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
        logger.info(f"User '{sanitize_email(email)}' is in 'Internal User Group', allowing access to '{path}' in app {app_id}")
        return True

    # Default: normal group-based check within the application
    logger.debug("Performing normal group-based authorization check within application")
    q = (
        select(User)
        .join(user_group_members, User.user_id == user_group_members.c.user_id)
        .join(UserGroup, user_group_members.c.user_group_id == UserGroup.group_id)
        .join(user_group_url_group_associations, UserGroup.group_id == user_group_url_group_associations.c.user_group_id)
        .join(UrlGroup, user_group_url_group_associations.c.url_group_id == UrlGroup.group_id)
        .join(Url, UrlGroup.group_id == Url.url_group_id)
        .where(
            and_(
                User.email == email, 
                Url.path == path,
                UrlGroup.app_id == app_id
            )
        )
    )
    result = await session.execute(q)
    user_found = result.scalar_one_or_none() is not None
    
    if user_found:
        logger.info(f"User '{sanitize_email(email)}' has access to '{path}' in app {app_id} through group membership")
    else:
        logger.warning(f"User '{sanitize_email(email)}' denied access to '{path}' in app {app_id} - no matching group permissions found")
    
    return user_found

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

async def get_all_user_groups(session: AsyncSession) -> List[UserGroup]:
    """Get all user groups."""
    logger.debug("Fetching all user groups")
    result = await session.execute(select(UserGroup).order_by(UserGroup.name))
    groups = result.scalars().all()
    logger.debug(f"Found {len(groups)} user groups")
    return groups

async def get_user_count_in_group(session: AsyncSession, group_id: int) -> int:
    """Get the number of users in a user group."""
    logger.debug(f"Counting users in group {group_id}")
    from sqlalchemy import func
    result = await session.execute(
        select(func.count(user_group_members.c.user_id))
        .where(user_group_members.c.user_group_id == group_id)
    )
    count = result.scalar()
    logger.debug(f"Found {count} users in group {group_id}")
    return count

async def get_users_in_group(session: AsyncSession, group_id: int) -> List[str]:
    """Get all user emails in a user group."""
    logger.debug(f"Fetching users in group {group_id}")
    from sqlalchemy import text
    result = await session.execute(text("""
        SELECT u.email 
        FROM users u 
        JOIN user_group_members ugm ON u.user_id = ugm.user_id 
        WHERE ugm.user_group_id = :group_id 
        ORDER BY u.email
    """), {"group_id": group_id})
    users = [row.email for row in result.fetchall()]
    logger.debug(f"Found {len(users)} users in group {group_id}")
    return users

async def get_url_groups_for_user_group(session: AsyncSession, user_group_id: int) -> List[UrlGroup]:
    """Get all URL groups associated with a user group."""
    logger.debug(f"Fetching URL groups for user group {user_group_id}")
    from sqlalchemy import text
    result = await session.execute(text("""
        SELECT ug.group_id, ug.name, ug.created_at, ug.protected, ug.app_id
        FROM url_groups ug
        JOIN user_group_url_group_associations a ON ug.group_id = a.url_group_id
        WHERE a.user_group_id = :user_group_id
        ORDER BY ug.name
    """), {"user_group_id": user_group_id})
    
    url_groups = []
    for row in result.fetchall():
        url_group = UrlGroup(
            group_id=row.group_id,
            name=row.name,
            created_at=row.created_at,
            protected=row.protected,
            app_id=row.app_id
        )
        url_groups.append(url_group)
    
    logger.debug(f"Found {len(url_groups)} URL groups for user group {user_group_id}")
    return url_groups

async def update_user_group(session: AsyncSession, group_id: int, name: Optional[str] = None) -> Optional[UserGroup]:
    """Update a user group."""
    logger.info(f"Updating user group {group_id}")
    group = await get_user_group(session, group_id)
    if not group:
        logger.warning(f"User group {group_id} not found for update")
        return None
    
    if name is not None:
        group.name = name
    
    await session.commit()
    await session.refresh(group)
    logger.info(f"Updated user group {group_id}")
    return group

async def delete_user_group(session: AsyncSession, group_id: int) -> bool:
    """Delete a user group."""
    logger.info(f"Deleting user group {group_id}")
    group = await get_user_group(session, group_id)
    if not group:
        logger.warning(f"User group {group_id} not found for deletion")
        return False
    
    # Prevent deletion if protected
    if getattr(group, 'protected', False):
        logger.warning(f"Cannot delete protected user group {group_id}")
        return False
    
    # Only allow deletion if there are no associations
    from sqlalchemy import text
    assoc_count = (await session.execute(
        text("SELECT COUNT(*) FROM user_group_url_group_associations WHERE user_group_id = :gid"), 
        {"gid": group_id}
    )).scalar()
    
    if assoc_count > 0:
        logger.warning(f"Cannot delete user group {group_id} with existing associations")
        return False
    
    await session.delete(group)
    await session.commit()
    logger.info(f"Deleted user group {group_id}")
    return True

# Add user to user group
async def add_user_to_group(session: AsyncSession, group_id: int, email: str) -> bool:
    logger.info(f"Adding user '{sanitize_email(email)}' to group ID: {group_id}")
    # First get the user by email
    user = await get_user(session, email)
    if not user:
        logger.warning(f"User '{sanitize_email(email)}' not found, cannot add to group")
        return False
    
    try:
        stmt = insert(user_group_members).values(user_group_id=group_id, user_id=user.user_id)
        await session.execute(stmt)
        await session.commit()
        logger.info(f"Successfully added user '{sanitize_email(email)}' to group ID: {group_id}")
        return True
    except IntegrityError:
        await session.rollback()
        logger.info(f"User '{sanitize_email(email)}' is already in group ID: {group_id}")
        return True  # Consider this a success since the user is already in the group

# Application CRUD
async def create_application(session: AsyncSession, name: str, host: str, description: Optional[str] = None) -> Application:
    logger.info(f"Creating new application: {name} with host: {host}")
    try:
        app = Application(name=name, host=host, description=description)
        session.add(app)
        await session.commit()
        await session.refresh(app)
        logger.info(f"Created application with ID: {app.app_id}")
        return app
    except IntegrityError:
        await session.rollback()
        logger.warning(f"Failed to create application '{name}' with host '{host}' - duplicate name/host")
        raise ValueError(f"Application with name '{name}' or host '{host}' already exists")

async def get_application(session: AsyncSession, app_id: int) -> Optional[Application]:
    result = await session.execute(select(Application).where(Application.app_id == app_id))
    return result.scalar_one_or_none()

async def get_application_by_name(session: AsyncSession, name: str) -> Optional[Application]:
    result = await session.execute(select(Application).where(Application.name == name))
    return result.scalar_one_or_none()

async def get_application_by_host(session: AsyncSession, host: str) -> Optional[Application]:
    result = await session.execute(select(Application).where(Application.host == host))
    return result.scalar_one_or_none()

async def get_all_applications(session: AsyncSession) -> List[Application]:
    result = await session.execute(select(Application).order_by(Application.name))
    return result.scalars().all()

async def get_all_applications_with_url_groups_count(session: AsyncSession) -> List[Application]:
    """Get all applications with URL groups count."""
    logger.debug("Fetching all applications with URL groups count")
    from sqlalchemy import text
    
    # Get applications with URL groups count
    result = await session.execute(
        text("""
            SELECT 
                a.app_id, 
                a.name, 
                a.host, 
                a.description, 
                a.created_at,
                COUNT(ug.group_id) as url_groups_count
            FROM applications a
            LEFT JOIN url_groups ug ON a.app_id = ug.app_id
            GROUP BY a.app_id, a.name, a.host, a.description, a.created_at
            ORDER BY a.name
        """)
    )
    
    applications = []
    for row in result.fetchall():
        app = Application(
            app_id=row.app_id,
            name=row.name,
            host=row.host,
            description=row.description,
            created_at=row.created_at
        )
        app.url_groups_count = row.url_groups_count
        applications.append(app)
    
    logger.debug(f"Found {len(applications)} applications with URL groups count")
    return applications

async def update_application(session: AsyncSession, app_id: int, name: Optional[str] = None, host: Optional[str] = None, description: Optional[str] = None) -> Optional[Application]:
    app = await get_application(session, app_id)
    if not app:
        return None
    
    if name is not None:
        app.name = name
    if host is not None:
        app.host = host
    if description is not None:
        app.description = description
    
    try:
        await session.commit()
        await session.refresh(app)
        return app
    except IntegrityError:
        await session.rollback()
        raise ValueError(f"Application with name '{name}' or host '{host}' already exists")

async def delete_application(session: AsyncSession, app_id: int) -> bool:
    app = await get_application(session, app_id)
    if not app:
        return False
    
    await session.delete(app)
    await session.commit()
    return True

# UrlGroup CRUD
async def create_url_group(session: AsyncSession, name: str, app_id: Optional[int] = None) -> UrlGroup:
    logger.info(f"Creating new URL group: {name} for application ID: {app_id}")
    try:
        group = UrlGroup(name=name, app_id=app_id)
        session.add(group)
        await session.commit()
        await session.refresh(group)
        logger.info(f"Created URL group with ID: {group.group_id}")
        return group
    except IntegrityError:
        await session.rollback()
        logger.warning(f"Failed to create URL group '{name}' for application ID {app_id} - duplicate name")
        raise ValueError(f"URL group with name '{name}' already exists for this application")

async def get_url_group(session: AsyncSession, group_id: int) -> Optional[UrlGroup]:
    logger.debug(f"Looking up URL group with ID: {group_id}")
    result = await session.execute(select(UrlGroup).where(UrlGroup.group_id == group_id))
    group = result.scalar_one_or_none()
    if group:
        logger.debug(f"Found URL group: {group.name}")
    else:
        logger.debug(f"URL group not found for ID: {group_id}")
    return group

async def list_url_groups_by_application(session: AsyncSession, app_id: Optional[int] = None) -> List[UrlGroup]:
    logger.debug(f"Listing URL groups for application ID: {app_id}")
    if app_id is None:
        # Get URL groups that don't belong to any application (system groups)
        result = await session.execute(select(UrlGroup).where(UrlGroup.app_id.is_(None)).order_by(UrlGroup.name))
    else:
        result = await session.execute(select(UrlGroup).where(UrlGroup.app_id == app_id).order_by(UrlGroup.name))
    groups = result.scalars().all()
    logger.debug(f"Found {len(groups)} URL groups")
    return groups

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
    try:
        stmt = insert(user_group_url_group_associations).values(user_group_id=user_group_id, url_group_id=url_group_id)
        await session.execute(stmt)
        await session.commit()
        logger.info(f"Successfully linked user group ID: {user_group_id} to URL group ID: {url_group_id}")
        return True
    except IntegrityError:
        await session.rollback()
        logger.info(f"User group ID: {user_group_id} is already linked to URL group ID: {url_group_id}")
        return True  # Consider this a success since the association already exists

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
