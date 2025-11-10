"""
Database abstraction layer for user management.
This provides a clean interface for user storage operations.
"""

from typing import Optional, List
from datetime import datetime

from sqlmodel import Session, select, SQLModel, create_engine
from sqlalchemy import func

from app.auth.models import User, UserInDB, AuthUser
from app.auth.exceptions import UserNotFoundError, UserAlreadyExistsError
from app.log import app_logger
from app.settings import settings


engine = create_engine(
    settings.DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}
)


def init_db():
    SQLModel.metadata.create_all(engine)


class UserDatabase:
    """SQLite-backed user database using SQLModel."""
    
    def __init__(self):
        init_db()
    
    def create_user(self, email: str, hashed_password: str, full_name: str) -> User:
        """Create a new user."""
        with Session(engine) as session:
            existing = session.exec(select(AuthUser).where(AuthUser.email == email)).first()
            if existing:
                raise UserAlreadyExistsError()
            now = datetime.utcnow()
            db_user = AuthUser(
                email=email,
                full_name=full_name,
                hashed_password=hashed_password,
                is_active=True,
                created_at=now,
                updated_at=now,
            )
            session.add(db_user)
            session.commit()
            session.refresh(db_user)
            app_logger.info(f"User created: {email} (ID: {db_user.id})")
            return User(
                id=db_user.id,
                email=db_user.email,
                full_name=db_user.full_name,
                is_active=db_user.is_active,
                created_at=db_user.created_at,
                updated_at=db_user.updated_at,
            )
    
    def get_user_by_email(self, email: str) -> Optional[UserInDB]:
        """Get user by email."""
        with Session(engine) as session:
            db_user = session.exec(select(AuthUser).where(AuthUser.email == email)).first()
            if not db_user:
                return None
            return UserInDB(
                id=db_user.id,
                email=db_user.email,
                full_name=db_user.full_name,
                is_active=db_user.is_active,
                created_at=db_user.created_at,
                updated_at=db_user.updated_at,
                hashed_password=db_user.hashed_password,
            )
    
    def get_user_by_id(self, user_id: int) -> Optional[UserInDB]:
        """Get user by ID."""
        with Session(engine) as session:
            db_user = session.get(AuthUser, user_id)
            if not db_user:
                return None
            return UserInDB(
                id=db_user.id,
                email=db_user.email,
                full_name=db_user.full_name,
                is_active=db_user.is_active,
                created_at=db_user.created_at,
                updated_at=db_user.updated_at,
                hashed_password=db_user.hashed_password,
            )
    
    def get_user_public_by_id(self, user_id: int) -> Optional[User]:
        """Get public user data by ID (without password)."""
        with Session(engine) as session:
            db_user = session.get(AuthUser, user_id)
            if not db_user:
                return None
            return User(
                id=db_user.id,
                email=db_user.email,
                full_name=db_user.full_name,
                is_active=db_user.is_active,
                created_at=db_user.created_at,
                updated_at=db_user.updated_at,
            )
    
    def update_user(self, user_id: int, **updates) -> Optional[User]:
        """Update user data."""
        with Session(engine) as session:
            db_user = session.get(AuthUser, user_id)
            if not db_user:
                return None
            for key, value in updates.items():
                if hasattr(db_user, key):
                    setattr(db_user, key, value)
            db_user.updated_at = datetime.utcnow()
            session.add(db_user)
            session.commit()
            session.refresh(db_user)
            app_logger.info(f"User updated: {db_user.email} (ID: {db_user.id})")
            return User(
                id=db_user.id,
                email=db_user.email,
                full_name=db_user.full_name,
                is_active=db_user.is_active,
                created_at=db_user.created_at,
                updated_at=db_user.updated_at,
            )
    
    def delete_user(self, user_id: int) -> bool:
        """Delete a user."""
        with Session(engine) as session:
            db_user = session.get(AuthUser, user_id)
            if not db_user:
                return False
            session.delete(db_user)
            session.commit()
            app_logger.info(f"User deleted: {db_user.email} (ID: {db_user.id})")
            return True
    
    def delete_user_by_email(self, email: str) -> bool:
        """Delete a user by email."""
        with Session(engine) as session:
            db_user = session.exec(select(AuthUser).where(AuthUser.email == email)).first()
            if not db_user:
                return False
            session.delete(db_user)
            session.commit()
            app_logger.info(f"User deleted by email: {email} (ID: {db_user.id})")
            return True
    
    def clear_all_users(self) -> int:
        """Remove all users. Returns number of users removed."""
        with Session(engine) as session:
            users = session.exec(select(AuthUser)).all()
            count = len(users)
            for u in users:
                session.delete(u)
            session.commit()
            app_logger.warning(f"All users cleared from database (count={count})")
            return count
    
    def list_users(self, limit: int = 100, offset: int = 0) -> List[User]:
        """List users (for admin purposes)."""
        with Session(engine) as session:
            stmt = select(AuthUser).offset(offset).limit(limit)
            rows = session.exec(stmt).all()
            return [
                User(
                    id=row.id,
                    email=row.email,
                    full_name=row.full_name,
                    is_active=row.is_active,
                    created_at=row.created_at,
                    updated_at=row.updated_at,
                )
                for row in rows
            ]
    
    def get_user_count(self) -> int:
        """Get total number of users."""
        with Session(engine) as session:
            return session.exec(select(func.count()).select_from(AuthUser)).one()


# Global database instance
user_db = UserDatabase()


