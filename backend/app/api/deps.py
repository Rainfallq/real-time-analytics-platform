"""
API dependencies
"""
from app.db.session import get_db
from fastapi.security import OAuth2PasswordBearer
from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User, UserRole
from app.core.security import decode_token
from sqlalchemy import select

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/login",
    scheme_name="JWT"
)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Dependency to get current authenticated user
    
    Usage:
        @app.get("/protected")
        async def protected_route(user: User = Depends(get_current_user)):
            return {"user_id": user.id}
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"}
    )

    # Decode token
    payload = decode_token(token)
    if payload is None:
        return credentials_exception

    # Validate token type
    token_type: str = payload.get("type")
    if token_type != "access":
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    # Extract user_id
    user_id_str: str = payload.get("sub")
    if user_id_str is None:
        return credentials_exception
    
    try: 
        from uuid import UUID
        user_id = UUID(user_id_str)
    except ValueError:
        return credentials_exception
    
    # Get user from database
    result = await db.excecute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()

    if user is None:
        return credentials_exception
    
    return user


def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Dependency to get current active user (is_active=True)
    
    Usage:
        @app.get("/active-only")
        async def active_route(user: User = Depends(get_current_active_user)):
            return {"user_id": user.id}
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )
    return current_user


def get_current_verified_user(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """
    Dependency to get current verified user (is_verified=True)
    """
    if not current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email is not verified"
        )
    return current_user


def require_role(required_role: UserRole):
    """
    Dependency factory for role-based access control
    
    Usage:
        @app.get("/admin-only")
        async def admin_route(user: User = Depends(require_role(UserRole.ADMIN))):
            return {"message": "Admin access"}
    """
    async def role_checker(
        current_user: User = Depends(get_current_active_user)
    ) -> User:
        if current_user.role != required_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role {required_role.value} required"
            )
        return current_user
    
    return role_checker


# Export commonly used dependencies
__all__ = [
    "get_db",
    "get_current_user",
    "get_current_active_user",
    "get_current_verified_user",
    "require_role"
    ]