"""
auth.py

Routes for user authentication and account management.

Endpoints:
    POST /auth/register             - Register a new user account
    POST /auth/login                - Authenticate user and get JWT token
    GET /auth/me                    - Get current authenticated user's profile
    POST /auth/request-password-reset - Request password reset email
    POST /auth/reset-password       - Reset password using valid reset token

Security:
    Uses OAuth2 with JWT tokens. Protected endpoints require Bearer token in Authorization header.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.database import get_db
from app.db.models import User
from app.schemas.auth import LoginRequest, Token, TokenData, UserCreate, UserResponse
from app.services.auth import create_access_token

settings = get_settings()
router = APIRouter(prefix="/auth", tags=["auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


async def get_current_user(
    token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)
):
    """
    Dependency to extract and validate the current authenticated user from JWT token.

    Args:
        token: JWT bearer token from Authorization header.
        db: Database session.

    Returns:
        User object if token is valid.

    Raises:
        HTTPException: 401 Unauthorized if token is invalid, expired, or user not found.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        token_data = TokenData(email=email)
    except JWTError:
        raise credentials_exception

    result = await db.execute(select(User).filter(User.email == token_data.email))
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exception
    return user


# ---------------------------------------------------------------------------
# User Registration and Login
# ---------------------------------------------------------------------------


@router.post("/register", response_model=UserResponse)
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    """
    Register a new user account.

    Args:
        user_data: UserCreate schema with email, username, and password.
        db: Database session.

    Returns:
        UserResponse with the created user's details.

    Raises:
        HTTPException: 400 Bad Request if email or username already exists.
    """
    # Check if user exists
    result = await db.execute(select(User).filter(User.email == user_data.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered"
        )

    result = await db.execute(select(User).filter(User.username == user_data.username))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Username already taken"
        )

    # Create new user
    user = User(email=user_data.email, username=user_data.username)
    user.set_password(user_data.password)

    db.add(user)
    await db.commit()
    await db.refresh(user)

    return user


@router.post("/login", response_model=Token)
async def login(login_data: LoginRequest, db: AsyncSession = Depends(get_db)):
    """
    Authenticate user with email and password, return JWT access token.

    Args:
        login_data: LoginRequest schema with email and password.
        db: Database session.

    Returns:
        Token with access_token and token_type ("bearer").

    Raises:
        HTTPException: 401 Unauthorized if email/password combination is invalid.
    """
    result = await db.execute(select(User).filter(User.email == login_data.email))
    user = result.scalar_one_or_none()

    if not user or not user.verify_password(login_data.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}


# ---------------------------------------------------------------------------
# User Profile
# ---------------------------------------------------------------------------


@router.get("/me", response_model=UserResponse)
async def read_users_me(current_user: User = Depends(get_current_user)):
    """
    Get the current authenticated user's profile information.

    Requires valid JWT token in Authorization header.

    Args:
        current_user: Current authenticated user (injected via get_current_user).

    Returns:
        UserResponse with the authenticated user's details.

    Raises:
        HTTPException: 401 Unauthorized if no valid token provided.
    """
    return current_user


# ---------------------------------------------------------------------------
# Password Reset
# ---------------------------------------------------------------------------


@router.post("/request-password-reset")
async def request_password_reset(email: EmailStr, db: AsyncSession = Depends(get_db)):
    """
    Request a password reset token for the given email address.

    If an account exists, a reset token is generated (caller should send reset link via email).
    Returns success message regardless to avoid email enumeration.

    Args:
        email: Email address associated with the account.
        db: Database session.

    Returns:
        JSON message indicating reset link will be sent if account exists.

    Note:
        Always returns success message to prevent user enumeration attacks.
    """
    result = await db.execute(select(User).filter(User.email == email))
    user = result.scalar_one_or_none()
    if user:
        user.generate_reset_token()
        await db.commit()
        return {
            "message": "If an account exists with this email, a password reset link will be sent"
        }
    return {
        "message": "If an account exists with this email, a password reset link will be sent"
    }


@router.post("/reset-password")
async def reset_password(
    token: str, new_password: str, db: AsyncSession = Depends(get_db)
):
    """
    Reset a user's password using a valid reset token.

    Args:
        token: Password reset token (obtained from password reset email).
        new_password: New password to set for the account.
        db: Database session.

    Returns:
        JSON message confirming password has been reset.

    Raises:
        HTTPException: 400 Bad Request if token is invalid, expired, or not found.
    """
    result = await db.execute(select(User).filter(User.reset_token == token))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    user.set_password(new_password)
    user.clear_reset_token()
    await db.commit()

    return {"message": "Password has been reset successfully"}
