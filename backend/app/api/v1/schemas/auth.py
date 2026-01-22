from pydantic import BaseModel, EmailStr, Field, field_validator, ConfigDict
from uuid import UUID
from datetime import datetime



def validate_password_strength(v: str) -> str:
    if not any(c.isdigit() for c in v):
        raise ValueError("Password must contain at least one digit")
    return v

# Request schemas
class UserRegister(BaseModel):
    """Schemas for User Registration"""
    email: EmailStr = Field(..., description="User's email")
    username: str = Field(..., min_length=3, max_length=50, pattern=r"^\w+$")
    password: str = Field(..., min_length=8, max_length=255)
    
    @field_validator("password")
    @classmethod
    def validate_password(cls, v):
        return validate_password_strength(v)
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "email@example.com",
                "username": "unique_username",
                "password": "dhsajhdjashdjaDJndn__2"
            }
        }
    )

    
class UserLogin(BaseModel):
    """User login request"""
    email: EmailStr = Field(..., description="User's email")
    password: str = Field(...)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "user@example.com",
                "password": "SecuePsword213"
            }
        }
    )


class RefreshToken(BaseModel):
    """Token refresh request"""
    refresh_token: str = Field(..., description="Refresh token")


# Response schemas
class Token(BaseModel):
    """Token response"""
    access_token: str = Field(..., description="JWT Access token")
    refresh_token: str = Field(..., description="JWT Refresh token")
    token_type: str = Field(default="bearer", description="Token type")


class UserResponse(BaseModel):
    """User response schema"""
    id: UUID
    email: EmailStr
    username: str
    full_name: str | None = None
    role: str 
    is_active: bool
    is_verified: bool
    created_at: datetime
    last_login: datetime | None = None

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "email": "user@example.com",
                "username": "userusername",
                "full_name": "Name Surname",
                "role": "user",
                "is_active": True,
                "is_verified": False,
                "created_at": "2026-01-15T18:06:00Z",
                "last_login": None
            }
        }
    )


class UserUpdate(BaseModel):
    """User data update request"""
    full_name: str | None = Field(default=None, min_length=3, max_length=255)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "full_name": "Will Smith"
            }
        }
    )


class PasswordChange(BaseModel):
    """Password Change request"""
    current_password: str = Field(..., description="Current password")
    new_password: str = Field(..., min_length=8, max_length=255)

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v):
        return validate_password_strength(v)
    

# Internal schemas
class TokenData(BaseModel):
    """Token data"""
    user_id: UUID | None = None
    token_type: str | None = None
