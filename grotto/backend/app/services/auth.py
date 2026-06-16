"""
auth.py

Authentication service for JWT token generation and management.

Provides utilities for creating and managing JSON Web Tokens (JWT) for user authentication.
Uses HS256 algorithm with configurable expiration times from application settings.

Example:
    from app.services.auth import create_access_token

    # Create a token for a user
    token_data = {"sub": "user@example.com"}
    access_token = create_access_token(data=token_data)

    # Token includes expiration timestamp automatically
    # Use in response: {"access_token": access_token, "token_type": "bearer"}
"""

from datetime import datetime, timedelta

from jose import jwt

from app.config import get_settings

settings = get_settings()


def create_access_token(data: dict) -> str:
    """
    Create a JWT access token with automatic expiration.

    Generates a JSON Web Token encoded with the provided data and an expiration
    timestamp. The token lifetime is configured via ACCESS_TOKEN_EXPIRE_MINUTES
    in application settings.

    Args:
        data: Dictionary containing claims to encode in the token.
              Typically includes {"sub": user_email} for user identification.

    Returns:
        Encoded JWT token as a string.

    Example:
        >>> token = create_access_token({"sub": "user@example.com"})
        >>> # Returns: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )
    return encoded_jwt
