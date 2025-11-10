"""
Authentication routes for user registration, login, and profile management.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse

from app.auth.models import User, UserCreate, LoginRequest, Token, RefreshTokenRequest
from app.auth.services import auth_service
from app.auth.dependencies import get_current_active_user
from app.auth.exceptions import (
    InvalidCredentialsError,
    UserAlreadyExistsError,
    InactiveUserError
)
from app.log import app_logger

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/register", response_model=User, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate):
    """
    Register a new user.
    
    Creates a new user account with the provided information.
    """
    try:
        user = await auth_service.register_user(user_data)
        return user
    except UserAlreadyExistsError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    except Exception as e:
        app_logger.error(f"Registration error for {user_data.email}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )


@router.post("/login", response_model=Token)
async def login(login_data: LoginRequest):
    """
    Login and get access tokens.
    
    Authenticates the user and returns access and refresh tokens.
    """
    try:
        # Authenticate user
        user = await auth_service.authenticate_user(login_data)
        
        # Create tokens
        tokens = await auth_service.create_tokens(user)
        
        return tokens
        
    except InvalidCredentialsError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except InactiveUserError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive"
        )
    except Exception as e:
        app_logger.error(f"Login error for {login_data.email}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )


@router.post("/refresh", response_model=Token)
async def refresh_token(refresh_request: RefreshTokenRequest):
    """
    Refresh access token using refresh token.
    
    Uses a valid refresh token to generate new access and refresh tokens.
    """
    try:
        tokens = await auth_service.refresh_access_token(refresh_request.refresh_token)
        return tokens
        
    except InvalidCredentialsError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        app_logger.error(f"Token refresh error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token refresh failed"
        )


@router.get("/me", response_model=User)
async def get_current_user_info(current_user: User = Depends(get_current_active_user)):
    """
    Get current user information.
    
    Returns the profile information of the currently authenticated user.
    """
    return current_user


@router.get("/get_user", response_model=User)
async def get_user(current_user: User = Depends(get_current_active_user)):
    """
    Get user information by JWT token.
    
    Returns detailed user information including id, email, full_name, 
    is_active status, and timestamps for the authenticated user.
    """
    return current_user


@router.post("/logout")
async def logout(current_user: User = Depends(get_current_active_user)):
    """
    Logout user.
    
    Note: Since JWT tokens are stateless, the client should discard the tokens.
    This endpoint is provided for logging purposes and potential future token blacklisting.
    """
    app_logger.info(f"User logged out: {current_user.email} (ID: {current_user.id})")
    return JSONResponse(
        content={"message": "Successfully logged out"},
        status_code=status.HTTP_200_OK
    )


@router.post("/create-admin", response_model=dict, include_in_schema=False)
async def create_admin_user():
    """
    Create a default admin user for testing purposes.
    
    This endpoint is excluded from the API documentation for security reasons.
    """
    from app.auth.database import user_db
    from app.auth.security import PasswordManager
    
    try:
        # Check if admin already exists
        admin_email = "admin@example.com"
        existing_admin = user_db.get_user_by_email(admin_email)
        if existing_admin:
            return {
                "message": "Admin user already exists",
                "user": {
                    "email": existing_admin.email,
                    "full_name": existing_admin.full_name
                }
            }
        
        # Create admin user
        password_manager = PasswordManager()
        hashed_password = password_manager.get_password_hash("admin")
        
        admin_user = user_db.create_user(
            email=admin_email,
            hashed_password=hashed_password,
            full_name="Admin User"
        )
        
        app_logger.info(f"Default admin user created: {admin_email}")
        
        return {
            "message": f"Admin user created successfully",
            "user": {
                "email": admin_user.email,
                "full_name": admin_user.full_name,
                "id": admin_user.id
            }
        }
        
    except Exception as e:
        app_logger.error(f"Error creating admin user: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create admin user"
        )


@router.delete("/debug/users", include_in_schema=False)
async def delete_user_by_email_debug(email: str):
    """
    DEBUG: Delete a single user by email from the in-memory DB.
    """
    from app.auth.database import user_db
    deleted = user_db.delete_user_by_email(email)
    if not deleted:
        raise HTTPException(status_code=404, detail="User not found")
    return {"message": "User deleted", "email": email}


@router.delete("/debug/users/all", include_in_schema=False)
async def clear_all_users_debug():
    """
    DEBUG: Clear all users from the in-memory DB.
    """
    from app.auth.database import user_db
    count = user_db.clear_all_users()
    return {"message": "All users cleared", "count": count}
