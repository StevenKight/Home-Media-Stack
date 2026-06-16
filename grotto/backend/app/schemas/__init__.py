"""
Schemas package for Magic Deck Helper API.

Exports all Pydantic models for easy importing across the application.
"""

# Authentication schemas
from app.schemas.auth import (
    LoginRequest,
    Token,
    TokenData,
    UserCreate,
    UserResponse,
)

__all__ = [
    # Auth
    "Token",
    "TokenData",
    "UserCreate",
    "LoginRequest",
    "UserResponse",
]
