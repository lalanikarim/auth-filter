from sqlalchemy import Column, Integer, String, ForeignKey, Table, DateTime, UniqueConstraint
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func
from .db import Base

class User(Base):
    __tablename__ = "users"
    email: Mapped[str] = mapped_column(String(255), primary_key=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())
    # Relationship to user_groups via association table
    groups = relationship("UserGroup", secondary="user_group_members", back_populates="users")

class UserGroup(Base):
    __tablename__ = "user_groups"
    group_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())
    # Relationship to users via association table
    users = relationship("User", secondary="user_group_members", back_populates="groups")
    # Relationship to url_groups via association table
    url_groups = relationship("UrlGroup", secondary="user_group_url_group_associations", back_populates="user_groups")

# Association table for users <-> user_groups (many-to-many)
user_group_members = Table(
    "user_group_members",
    Base.metadata,
    Column("user_group_id", Integer, ForeignKey("user_groups.group_id"), primary_key=True),
    Column("user_email", String(255), ForeignKey("users.email"), primary_key=True),
)

class UrlGroup(Base):
    __tablename__ = "url_groups"
    group_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())
    # Relationship to urls
    urls = relationship("Url", back_populates="url_group")
    # Relationship to user_groups via association table
    user_groups = relationship("UserGroup", secondary="user_group_url_group_associations", back_populates="url_groups")

class Url(Base):
    __tablename__ = "urls"
    url_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    path: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    url_group_id: Mapped[int] = mapped_column(Integer, ForeignKey("url_groups.group_id"))
    url_group = relationship("UrlGroup", back_populates="urls")

# Association table for user_groups <-> url_groups (many-to-many)
user_group_url_group_associations = Table(
    "user_group_url_group_associations",
    Base.metadata,
    Column("user_group_id", Integer, ForeignKey("user_groups.group_id"), primary_key=True),
    Column("url_group_id", Integer, ForeignKey("url_groups.group_id"), primary_key=True),
)
