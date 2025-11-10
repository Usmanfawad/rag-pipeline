"""
Authentication models and data structures.
"""

from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, EmailStr
from sqlmodel import SQLModel, Field as SQLField


class UserBase(BaseModel):
    """Base user model with common fields."""
    email: EmailStr
    full_name: str = Field(..., min_length=1, max_length=100)
    is_active: bool = True


class UserCreate(UserBase):
    """Schema for creating a new user."""
    password: str = Field(..., min_length=8, max_length=100)


class User(UserBase):
    """User model for API responses."""
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class UserInDB(User):
    """User model with hashed password for internal use."""
    hashed_password: str


class AuthUser(SQLModel, table=True):
    """SQLModel ORM for users table."""
    __tablename__ = "users"
    id: Optional[int] = SQLField(default=None, primary_key=True)
    email: EmailStr = SQLField(index=True, unique=True)
    full_name: str
    hashed_password: str
    is_active: bool = True
    created_at: datetime = SQLField(default_factory=datetime.utcnow)
    updated_at: datetime = SQLField(default_factory=datetime.utcnow)


class LoginRequest(BaseModel):
    """Schema for user login."""
    email: EmailStr
    password: str


class Token(BaseModel):
    """JWT token response."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenData(BaseModel):
    """Token payload data."""
    user_id: Optional[int] = None
    email: Optional[str] = None


class RefreshTokenRequest(BaseModel):
    """Schema for token refresh."""
    refresh_token: str


