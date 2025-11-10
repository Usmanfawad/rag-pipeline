"""
FastAPI dependencies for authentication.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.auth.models import User
from app.auth.services import auth_service
from app.auth.exceptions import InvalidCredentialsError, InactiveUserError
from app.log import app_logger

# Security scheme
security = HTTPBearer(auto_error=False)


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> User:
    """
    Get the current authenticated user from JWT token.
    
    Args:
        credentials: HTTP Bearer token credentials
        
    Returns:
        User: The authenticated user
        
    Raises:
        HTTPException: If authentication fails
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    try:
        user = await auth_service.verify_token_and_get_user(credentials.credentials)
        return user
    except InvalidCredentialsError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except InactiveUserError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user account",
        )
    except Exception as e:
        app_logger.error(f"Authentication dependency error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """
    Get the current active user (additional check for active status).
    
    Args:
        current_user: The authenticated user
        
    Returns:
        User: The active user
        
    Raises:
        HTTPException: If user is not active
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user account"
        )
    return current_user


async def get_optional_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> User | None:
    """
    Get the current user if authenticated, otherwise return None.
    Useful for endpoints that work with or without authentication.
    
    Args:
        credentials: HTTP Bearer token credentials
        
    Returns:
        User | None: The authenticated user or None
    """
    if not credentials:
        return None
    
    try:
        user = await auth_service.verify_token_and_get_user(credentials.credentials)
        return user
    except Exception:
        return None


def get_user_namespace(current_user: User = Depends(get_current_active_user)) -> str:
    """
    Get the namespace for the current user's documents.
    
    Args:
        current_user: The authenticated user
        
    Returns:
        str: User-specific namespace
    """
    return auth_service.create_user_namespace(current_user.id)


