from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import insert, update, delete, and_
from .models import User, UserGroup, UrlGroup, Url, user_group_members, user_group_url_group_associations
from typing import Optional

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
    stmt = insert(user_group_members).values(user_group_id=group_id, user_email=email).prefix_with("OR IGNORE")
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
    stmt = insert(user_group_url_group_associations).values(user_group_id=user_group_id, url_group_id=url_group_id).prefix_with("OR IGNORE")
    await session.execute(stmt)
    await session.commit()
    return True

# Authorization check
async def is_user_allowed(session: AsyncSession, email: str, url_path: str) -> bool:
    # Equivalent to the SQL in the design spec
    q = (
        select(User)
        .join(user_group_members, User.email == user_group_members.c.user_email)
        .join(UserGroup, user_group_members.c.user_group_id == UserGroup.group_id)
        .join(user_group_url_group_associations, UserGroup.group_id == user_group_url_group_associations.c.user_group_id)
        .join(UrlGroup, user_group_url_group_associations.c.url_group_id == UrlGroup.group_id)
        .join(Url, UrlGroup.group_id == Url.url_group_id)
        .where(and_(User.email == email, Url.path == url_path))
    )
    result = await session.execute(q)
    return result.scalar_one_or_none() is not None
