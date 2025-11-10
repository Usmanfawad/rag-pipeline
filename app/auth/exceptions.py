"""
Custom authentication exceptions.
"""

from fastapi import HTTPException, status


class AuthenticationError(HTTPException):
    """Base authentication error."""
    def __init__(self, detail: str = "Authentication failed"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"}
        )


class InvalidCredentialsError(AuthenticationError):
    """Invalid email or password error."""
    def __init__(self):
        super().__init__(detail="Incorrect email or password")


class TokenError(AuthenticationError):
    """Invalid or expired token error."""
    def __init__(self, detail: str = "Invalid or expired token"):
        super().__init__(detail=detail)


class UserNotFoundError(HTTPException):
    """User not found error."""
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )


class UserAlreadyExistsError(HTTPException):
    """User already exists error."""
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )


class InactiveUserError(HTTPException):
    """Inactive user error."""
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )


