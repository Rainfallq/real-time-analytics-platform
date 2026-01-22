from sqlalchemy.orm import DeclarativeBase, declared_attr
from sqlalchemy import Column, DateTime, func
from datetime import datetime


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models"""
    pass


class TimestampMixin:
    """Mixin to add created_at and updated_at timestamps"""

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="Record creation timestamp"
    )

    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="Record last update timestamp"
    )

class TableNameMixin:
    """Mixin to automatically generate table names from class names"""

    @declared_attr
    def __tablename__(cls) -> str:
        # Convert CamelCase to snake_case
        import re
        name = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', cls.__name__)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', name).lower() + 's'

