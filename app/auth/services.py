"""
Authentication service layer.
"""

from datetime import timedelta
from typing import Optional

from app.auth.models import User, UserCreate, LoginRequest, Token
from app.auth.database import user_db
from app.auth.security import PasswordManager, TokenManager
from app.auth.exceptions import (
    InvalidCredentialsError, 
    UserNotFoundError, 
    InactiveUserError,
    UserAlreadyExistsError
)
from app.settings import settings
from app.log import app_logger


class AuthService:
    """Authentication service."""
    
    def __init__(self):
        self.password_manager = PasswordManager()
        self.token_manager = TokenManager()
    
    async def register_user(self, user_data: UserCreate) -> User:
        """Register a new user."""
        try:
            # Hash password
            hashed_password = self.password_manager.get_password_hash(user_data.password)
            
            # Create user
            user = user_db.create_user(
                email=user_data.email,
                hashed_password=hashed_password,
                full_name=user_data.full_name
            )
            
            app_logger.info(f"User registered successfully: {user.email} (ID: {user.id})")
            return user
            
        except UserAlreadyExistsError:
            raise
        except Exception as e:
            app_logger.error(f"Registration error for {user_data.email}: {str(e)}")
            raise UserAlreadyExistsError()  # Generic error for security
    
    async def authenticate_user(self, login_data: LoginRequest) -> User:
        """Authenticate a user with email and password."""
        try:
            # Get user from database
            user_in_db = user_db.get_user_by_email(login_data.email)
            if not user_in_db:
                app_logger.warning(f"Login attempt with non-existent email: {login_data.email}")
                raise InvalidCredentialsError()
            
            # Verify password
            if not self.password_manager.verify_password(login_data.password, user_in_db.hashed_password):
                app_logger.warning(f"Failed login attempt for: {login_data.email}")
                raise InvalidCredentialsError()
            
            # Check if user is active
            if not user_in_db.is_active:
                app_logger.warning(f"Login attempt by inactive user: {login_data.email}")
                raise InactiveUserError()
            
            # Return public user data
            user = User(**{k: v for k, v in user_in_db.dict().items() if k != "hashed_password"})
            app_logger.info(f"User authenticated successfully: {user.email} (ID: {user.id})")
            return user
            
        except (InvalidCredentialsError, InactiveUserError):
            raise
        except Exception as e:
            app_logger.error(f"Authentication error for {login_data.email}: {str(e)}")
            raise InvalidCredentialsError()  # Generic error for security
    
    async def create_tokens(self, user: User) -> Token:
        """Create access and refresh tokens for a user."""
        try:
            # Create tokens
            access_token_expires = timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
            access_token = self.token_manager.create_access_token(
                data={"sub": user.id, "email": user.email}, 
                expires_delta=access_token_expires
            )
            
            refresh_token = self.token_manager.create_refresh_token(
                data={"sub": user.id, "email": user.email}
            )
            
            app_logger.info(f"Tokens created for user: {user.email} (ID: {user.id})")
            
            return Token(
                access_token=access_token,
                refresh_token=refresh_token,
                token_type="bearer",
                expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60  # Convert to seconds
            )
            
        except Exception as e:
            app_logger.error(f"Token creation error for user {user.id}: {str(e)}")
            raise InvalidCredentialsError()
    
    async def refresh_access_token(self, refresh_token: str) -> Token:
        """Refresh access token using refresh token."""
        try:
            # Verify refresh token
            token_data = self.token_manager.verify_token(refresh_token, "refresh")
            if not token_data:
                app_logger.warning("Invalid refresh token provided")
                raise InvalidCredentialsError()
            
            # Get user
            user_in_db = user_db.get_user_by_id(token_data.user_id)
            if not user_in_db or not user_in_db.is_active:
                app_logger.warning(f"User not found or inactive for refresh token: {token_data.user_id}")
                raise InvalidCredentialsError()
            
            # Create new tokens
            user = User(**{k: v for k, v in user_in_db.dict().items() if k != "hashed_password"})
            return await self.create_tokens(user)
            
        except InvalidCredentialsError:
            raise
        except Exception as e:
            app_logger.error(f"Token refresh error: {str(e)}")
            raise InvalidCredentialsError()
    
    async def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Get user by ID."""
        try:
            user_in_db = user_db.get_user_by_id(user_id)
            if not user_in_db:
                return None
            
            return User(**{k: v for k, v in user_in_db.dict().items() if k != "hashed_password"})
            
        except Exception as e:
            app_logger.error(f"Error getting user {user_id}: {str(e)}")
            return None
    
    async def verify_token_and_get_user(self, token: str) -> User:
        """Verify token and return the associated user."""
        try:
            # Verify token
            token_data = self.token_manager.verify_token(token, "access")
            if not token_data:
                raise InvalidCredentialsError()
            
            # Get user
            user_in_db = user_db.get_user_by_id(token_data.user_id)
            if not user_in_db:
                app_logger.warning(f"User not found for token: {token_data.user_id}")
                raise InvalidCredentialsError()
            
            if not user_in_db.is_active:
                app_logger.warning(f"Inactive user attempted access: {token_data.user_id}")
                raise InactiveUserError()
            
            return User(**{k: v for k, v in user_in_db.dict().items() if k != "hashed_password"})
            
        except (InvalidCredentialsError, InactiveUserError):
            raise
        except Exception as e:
            app_logger.error(f"Token verification error: {str(e)}")
            raise InvalidCredentialsError()
    
    def create_user_namespace(self, user_id: int) -> str:
        """Create a namespace for a user's documents."""
        return self.token_manager.create_user_namespace(user_id)


# Global service instance
auth_service = AuthService()


