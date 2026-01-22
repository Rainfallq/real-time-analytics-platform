from sqlalchemy import Column, String, Boolean, DateTime, Enum as SQLEnum, Index, func
from sqlalchemy.dialects.postgresql import UUID
import uuid
import enum

from app.db.base import Base, TimestampMixin




class UserRole(str, enum.Enum):
    ADMIN = "admin"
    USER = "user"
    VIEWER = "viewer"


class User(Base, TimestampMixin):
    """User Model for authentication"""
    
    __tablename__ = "users"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
        comment="User id"
    )

    username = Column(
        String(50),
        unique=True,
        index=True,
        nullable=False,
        comment="Username"
    )

    email = Column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
        comment="User email (login)"
    )

    password_hash = Column(
        String(255),
        nullable=False,
        comment="Hashed password"
    )

    full_name = Column(
        String(255),
        nullable=True,
        comment="User full name"
    )

    role = Column(
        SQLEnum(UserRole, name="user_role"),
        nullable=False,
        default=UserRole.USER,
        comment="User role for permissions"
    )

    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Is user account active"
    )

    is_verified = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Is email verified"
    )

    last_login = Column(    
        "last_login_at",
        DateTime(timezone=True),
        nullable=True,
        comment="Last login timestamp"
    )

    __table_args__ = (
        Index("ix_users_username_lower", func.lower(username), unique=True),
        )

    def __repr__(self):
        return f"<User {self.email}>"