from fastapi import APIRouter, status, Depends, HTTPException
from app.api.v1.schemas.auth import (
    UserResponse, UserRegister, UserLogin, PasswordChange, Token, RefreshToken,
    UserUpdate,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from app.models.user import User
from app.core.security import (
    verify_password, get_password_hash,
    create_access_token, create_refresh_token, decode_token
)
from datetime import datetime, timezone
from app.api.deps import get_current_active_user, get_db





router = APIRouter()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserRegister,
    db: AsyncSession = Depends(get_db)
):
    """
    Register a new user
    """
    query = select(User).where(
        or_(
            User.email == user_data.email,
            User.username == user_data.username
            )
    )

    result = await db.execute(query)
    existing_user = result.scalar_one_or_none()

    if existing_user:
        if existing_user.email == user_data.email:
            detail = "Email is already registered"
        else:
            detail = "Username is already taken"

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail
        )
    
    # Create new user
    new_user = User(
        email=user_data.email,
        username=user_data.username,
        password_hash=get_password_hash(user_data.password)
    )

    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    return new_user


@router.post("/login", response_model=Token)
async def login(
    credentials: UserLogin, 
    db: AsyncSession = Depends(get_db)
):
    filters = []
    if credentials.email: 
        filters.append(User.email == credentials.email)
    if credentials.username:
        filters.append(User.username == credentials.username)

    query = select(User).where(or_(*filters))
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if not user or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )
    
    # Update last login
    user.last_login = datetime.now(timezone.utc)
    await db.commit()

    access_token = create_access_token(
        data={"sub": str(user.id)}
    )
    refresh_token = create_refresh_token(
        data={"sub": str(user.id)}
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }


@router.post("/refresh", response_model=Token)
async def refresh_token(
    token_data: RefreshToken,
    db: AsyncSession = Depends(get_db)
):
    """
    Refresh access token using refresh token
    
    When access token expires, use this endpoint to get a new one
    """
    payload = decode_token(token_data.refresh_token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_type = payload.get("type")
    if token_type != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id_str: str = payload.get("sub")
    if user_id_str is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    try:
        from uuid import UUID
        user_id = UUID(user_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user ID in token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_access_token(
        data={"sub": str(user.id)}
    )

    refresh_token = create_refresh_token(
        data={"sub": str(user.id)}
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_active_user)
):
    """
    Get current user information
    
    Requires authentication (Bearer token in header)
    """
    return current_user


@router.put("/me", response_model=UserResponse)
async def update_current_user(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    if user_update.full_name is not None:
        current_user.full_name = user_update.full_name
    
    await db.commit()
    await db.refresh(current_user)

    return current_user


@router.post("/change-password", status_code=status.HTTP_200_OK)
async def change_password(
    password_data: PasswordChange,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    if not verify_password(password_data.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect password"
        )
    
    if password_data.current_password == password_data.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from the current one"
        )
    
    current_user.password_hash = get_password_hash(password_data.new_password)
    await db.commit()

    return {"message": "Password changed successfully"}
