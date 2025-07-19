from sqlalchemy import Column, Integer, String, ForeignKey, Table, DateTime, UniqueConstraint
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func
from .db import Base
from typing import Optional

class User(Base):
    __tablename__ = "users"
    user_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())
    # Relationship to user_groups via association table
    groups = relationship("UserGroup", secondary="user_group_members", back_populates="users")

class UserGroup(Base):
    __tablename__ = "user_groups"
    group_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())
    protected: Mapped[bool] = mapped_column(Integer, default=0, nullable=False)  # 0=False, 1=True
    # Relationship to users via association table
    users = relationship("User", secondary="user_group_members", back_populates="groups")
    # Relationship to url_groups via association table
    url_groups = relationship("UrlGroup", secondary="user_group_url_group_associations", back_populates="user_groups")

# Association table for users <-> user_groups (many-to-many)
user_group_members = Table(
    "user_group_members",
    Base.metadata,
    Column("user_group_id", Integer, ForeignKey("user_groups.group_id"), primary_key=True),
    Column("user_id", Integer, ForeignKey("users.user_id"), primary_key=True),
    # Composite unique constraint: user can only be in a group once
    UniqueConstraint('user_group_id', 'user_id', name='uq_user_group_member'),
)

class Application(Base):
    __tablename__ = "applications"
    app_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    host: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())
    # Relationship to url_groups
    url_groups = relationship("UrlGroup", back_populates="application")

class UrlGroup(Base):
    __tablename__ = "url_groups"
    group_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())
    protected: Mapped[bool] = mapped_column(Integer, default=0, nullable=False)  # 0=False, 1=True
    app_id: Mapped[int] = mapped_column(Integer, ForeignKey("applications.app_id"), nullable=True)
    # Relationship to application
    application = relationship("Application", back_populates="url_groups")
    # Relationship to urls
    urls = relationship("Url", back_populates="url_group")
    # Relationship to user_groups via association table
    user_groups = relationship("UserGroup", secondary="user_group_url_group_associations", back_populates="url_groups")
    
    # Composite unique constraint: name must be unique within an application (or globally if no app)
    __table_args__ = (
        UniqueConstraint('name', 'app_id', name='uq_url_group_name_per_app'),
    )

class Url(Base):
    __tablename__ = "urls"
    url_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    path: Mapped[str] = mapped_column(String(255), nullable=False)
    url_group_id: Mapped[int] = mapped_column(Integer, ForeignKey("url_groups.group_id"))
    url_group = relationship("UrlGroup", back_populates="urls")
    
    # Composite unique constraint: path must be unique within a url_group
    __table_args__ = (
        UniqueConstraint('path', 'url_group_id', name='uq_url_path_per_group'),
    )

# Association table for user_groups <-> url_groups (many-to-many)
user_group_url_group_associations = Table(
    "user_group_url_group_associations",
    Base.metadata,
    Column("user_group_id", Integer, ForeignKey("user_groups.group_id"), primary_key=True),
    Column("url_group_id", Integer, ForeignKey("url_groups.group_id"), primary_key=True),
)
