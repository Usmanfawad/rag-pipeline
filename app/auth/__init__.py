"""
Authentication package for the RAG Pipeline API.
"""

from app.auth.models import User, UserCreate, LoginRequest, Token, TokenData
from app.auth.services import auth_service
from app.auth.dependencies import (
    get_current_user, 
    get_current_active_user, 
    get_optional_current_user,
    get_user_namespace
)
from app.auth.exceptions import (
    AuthenticationError,
    InvalidCredentialsError,
    TokenError,
    UserNotFoundError,
    UserAlreadyExistsError,
    InactiveUserError
)

__all__ = [
    # Models
    "User",
    "UserCreate", 
    "LoginRequest",
    "Token",
    "TokenData",
    
    # Services
    "auth_service",
    
    # Dependencies
    "get_current_user",
    "get_current_active_user",
    "get_optional_current_user",
    "get_user_namespace",
    
    # Exceptions
    "AuthenticationError",
    "InvalidCredentialsError",
    "TokenError",
    "UserNotFoundError",
    "UserAlreadyExistsError",
    "InactiveUserError",
]


