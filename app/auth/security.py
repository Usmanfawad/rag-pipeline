"""
Security utilities for authentication.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import secrets

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.settings import settings
from app.auth.models import TokenData
from app.auth.exceptions import TokenError
from app.log import app_logger

# Password hashing
# Use bcrypt_sha256 to avoid the 72-byte bcrypt input limit by pre-hashing
pwd_context = CryptContext(schemes=["bcrypt_sha256"], deprecated="auto")


class PasswordManager:
    """Handles password operations."""
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash."""
        try:
            return pwd_context.verify(plain_password, hashed_password)
        except Exception as e:
            app_logger.error(f"Password verification error: {str(e)}")
            return False
    
    @staticmethod
    def get_password_hash(password: str) -> str:
        """Hash a password."""
        try:
            # Ensure password is not too long for bcrypt (72 bytes max)
            if len(password.encode('utf-8')) > 72:
                password = password[:72]
                app_logger.warning("Password truncated to 72 bytes for bcrypt compatibility")
            
            return pwd_context.hash(password)
        except Exception as e:
            app_logger.error(f"Password hashing error: {str(e)}")
            raise TokenError("Password hashing failed")


class TokenManager:
    """Handles JWT token operations."""
    
    @staticmethod
    def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        """Create a JWT access token."""
        try:
            to_encode = data.copy()
            # Standardize subject as string per RFC7519
            if "sub" in to_encode:
                to_encode["sub"] = str(to_encode["sub"])
            if expires_delta:
                expire = datetime.utcnow() + expires_delta
            else:
                expire = datetime.utcnow() + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
            
            to_encode.update({
                "exp": expire, 
                "type": "access",
                "jti": secrets.token_urlsafe(16)  # Unique token ID
            })
            
            return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
        except Exception as e:
            app_logger.error(f"Access token creation error: {str(e)}")
            raise TokenError("Token creation failed")
    
    @staticmethod
    def create_refresh_token(data: Dict[str, Any]) -> str:
        """Create a JWT refresh token."""
        try:
            to_encode = data.copy()
            if "sub" in to_encode:
                to_encode["sub"] = str(to_encode["sub"])
            expire = datetime.utcnow() + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
            to_encode.update({
                "exp": expire, 
                "type": "refresh",
                "jti": secrets.token_urlsafe(16)  # Unique token ID
            })
            
            return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
        except Exception as e:
            app_logger.error(f"Refresh token creation error: {str(e)}")
            raise TokenError("Refresh token creation failed")
    
    @staticmethod
    def verify_token(token: str, token_type: str = "access") -> Optional[TokenData]:
        """Verify and decode a JWT token."""
        try:
            payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
            
            # Verify token type
            if payload.get("type") != token_type:
                app_logger.warning(f"Token type mismatch. Expected: {token_type}, Got: {payload.get('type')}")
                return None
            
            user_id = payload.get("sub")
            email = payload.get("email")
            
            if user_id is None or email is None:
                app_logger.warning("Token missing required fields (sub or email)")
                return None
            
            # Coerce user_id back to int if possible
            try:
                coerced_user_id = int(user_id)
            except (TypeError, ValueError):
                coerced_user_id = None
            
            return TokenData(user_id=coerced_user_id, email=email)
            
        except JWTError as e:
            app_logger.warning(f"JWT verification error: {str(e)}")
            return None
        except Exception as e:
            app_logger.error(f"Token verification error: {str(e)}")
            return None
    
    @staticmethod
    def create_user_namespace(user_id: int) -> str:
        """Create a namespace for a user's documents."""
        return f"user_{user_id}"
    
    @staticmethod
    def parse_user_namespace(namespace: str) -> Optional[int]:
        """Parse a user namespace to extract user_id."""
        if not namespace.startswith("user_"):
            return None
        
        try:
            user_id = int(namespace.split("_", 1)[1])
            return user_id
        except (ValueError, IndexError):
            return None


