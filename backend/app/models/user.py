from sqlalchemy import Column, String, Boolean, DateTime, Index
from sqlalchemy import func
from sqlalchemy import Uuid, JSON
from sqlalchemy.dialects.postgresql import JSONB
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
        Uuid(as_uuid=True),
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
        String(20),
        nullable=False,
        default=UserRole.USER.value,
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
        server_default=func.now(),
        comment="Last login timestamp"
    )

    __table_args__ = (
        Index("ix_users_username_lower", func.lower(username), unique=True),
        )

    def __repr__(self):
        return f"<User {self.email}>"