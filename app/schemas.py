from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime

# User schemas
class UserBase(BaseModel):
    email: EmailStr

class UserCreate(UserBase):
    pass

class UserRead(UserBase):
    created_at: datetime
    class Config:
        from_attributes = True

# UserGroup schemas
class UserGroupBase(BaseModel):
    name: str

class UserGroupCreate(UserGroupBase):
    pass

class UserGroupRead(UserGroupBase):
    group_id: int
    created_at: datetime
    users: Optional[List[UserRead]] = None
    class Config:
        from_attributes = True

# Application schemas
class ApplicationBase(BaseModel):
    name: str
    host: str
    description: Optional[str] = None

class ApplicationCreate(ApplicationBase):
    pass

class ApplicationRead(ApplicationBase):
    app_id: int
    created_at: datetime
    url_groups: Optional[List['UrlGroupRead']] = None
    class Config:
        from_attributes = True

# UrlGroup schemas
class UrlGroupBase(BaseModel):
    name: str
    app_id: Optional[int] = None

class UrlGroupCreate(UrlGroupBase):
    pass

class UrlGroupRead(UrlGroupBase):
    group_id: int
    created_at: datetime
    app_id: Optional[int] = None
    application: Optional[ApplicationRead] = None
    urls: Optional[List['UrlRead']] = None
    class Config:
        from_attributes = True

# Url schemas
class UrlBase(BaseModel):
    path: str

class UrlCreate(UrlBase):
    pass

class UrlRead(UrlBase):
    url_id: int
    url_group_id: Optional[int]
    class Config:
        from_attributes = True

# Association schemas
class UserGroupUrlGroupAssociationCreate(BaseModel):
    user_group_id: int
    url_group_id: int

class SuccessResponse(BaseModel):
    success: bool = True

class AuthRequest(BaseModel):
    token: str

class AuthResponse(BaseModel):
    email: EmailStr
    valid: bool

class AuthorizeRequest(BaseModel):
    email: EmailStr
    url_path: str

class AuthorizeResponse(BaseModel):
    allowed: bool

# For forward references
UrlGroupRead.update_forward_refs()
ApplicationRead.update_forward_refs()
