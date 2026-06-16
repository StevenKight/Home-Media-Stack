"""
models.py

SQLAlchemy database models for user authentication and account management.

Defines the User model with password hashing, email verification, and password
reset functionality using bcrypt for secure password storage.

Example:
    from app.db.models import User
    from app.db.database import get_db

    # Create a new user
    user = User(email="user@example.com", username="johndoe")
    user.set_password("secure_password")
    db.add(user)
    await db.commit()

    # Verify password
    if user.verify_password("attempted_password"):
        print("Password is correct")

    # Generate password reset token
    user.generate_reset_token()
    await db.commit()
"""

import secrets

from passlib.context import CryptContext
from sqlalchemy import Boolean, Column, DateTime, Integer, String
from sqlalchemy.sql import func

from .database import Base

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class User(Base):
    """
    User model for authentication and account management.

    Stores user credentials, profile information, and account status.
    Passwords are hashed using bcrypt. Includes methods for password
    verification, password reset token generation, and account management.

    Attributes:
        id: Primary key, auto-incrementing user ID.
        email: Unique email address for user login and communication.
        username: Unique username for user identification.
        hashed_password: Bcrypt-hashed password (never store plain text).
        role: User role for permissions ("user", "admin", "moderator").
        is_superuser: Flag for superuser/root access.
        is_active: Whether account is active and can log in.
        email_verified: Whether email address has been verified.
        created_at: Timestamp of account creation.
        updated_at: Timestamp of last account update (auto-updated).
        reset_token: Secure token for password reset (nullable).
    """

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, nullable=False)
    username = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="user")  # Roles: "user", "admin", "moderator"
    is_superuser = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    email_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    reset_token = Column(String, unique=True, nullable=True)

    def verify_password(self, password: str) -> bool:
        """
        Check if a plain password matches the hashed password.

        Args:
            password: Plain text password to verify.

        Returns:
            True if password matches, False otherwise.

        Example:
            >>> if user.verify_password("user_input"):
            >>>     # Password is correct
        """
        return pwd_context.verify(password, self.hashed_password)

    def set_password(self, password: str):
        """
        Hash and store a password securely.

        Uses bcrypt to hash the password before storing. Never stores
        plain text passwords.

        Args:
            password: Plain text password to hash and store.

        Example:
            >>> user.set_password("new_secure_password")
            >>> db.commit()
        """
        self.hashed_password = pwd_context.hash(password)

    def generate_reset_token(self):
        """
        Generate a secure password reset token.

        Creates a URL-safe random token for password reset links.
        Token should be sent to user's verified email and expires
        after a configured time period.

        Example:
            >>> user.generate_reset_token()
            >>> db.commit()
            >>> send_email(user.email, f"Reset link: /reset?token={user.reset_token}")
        """
        self.reset_token = secrets.token_urlsafe(32)

    def clear_reset_token(self):
        """
        Clear password reset token after use.

        Should be called after successful password reset to invalidate
        the token and prevent reuse.

        Example:
            >>> user.set_password("new_password")
            >>> user.clear_reset_token()
            >>> db.commit()
        """
        self.reset_token = None
