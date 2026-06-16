"""
auth.py

Pydantic models for authentication and user management.

Handles JWT token responses, user registration, login requests, and user profile data.

Example:
    from auth import UserCreate, LoginRequest, UserResponse

    # User registration
    new_user = UserCreate(
        email="user@example.com",
        username="john_doe",
        password="secure_password"
    )

    # User login
    login_data = LoginRequest(email="user@example.com", password="secure_password")

    # User profile (returned from API)
    user = UserResponse(
        id=1,
        email="user@example.com",
        username="john_doe",
        is_active=True,
        email_verified=True,
        role="user",
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    email: str | None = None


class UserCreate(BaseModel):
    email: EmailStr
    username: str
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    email: str
    username: str
    is_active: bool
    email_verified: bool
    role: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
