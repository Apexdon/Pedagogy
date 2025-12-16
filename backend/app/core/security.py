"""
Security Module

Password hashing and JWT token management for authentication.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from jose import JWTError, jwt
import bcrypt

from app.config import settings

# JWT Algorithm
ALGORITHM = "HS256"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed password."""
    return bcrypt.checkpw(
        plain_password.encode('utf-8'),
        hashed_password.encode('utf-8')
    )


def get_password_hash(password: str) -> str:
    """Generate a bcrypt hash for a password."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token.

    Args:
        data: Payload data (should include 'sub' for user_id, 'org_id', 'role')
        expires_delta: Optional custom expiration time

    Returns:
        Encoded JWT token string
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({
        "exp": expire,
        "type": "access"
    })

    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(data: Dict[str, Any]) -> str:
    """
    Create a JWT refresh token with longer expiration.

    Args:
        data: Payload data (should include 'sub' for user_id)

    Returns:
        Encoded JWT refresh token string
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    to_encode.update({
        "exp": expire,
        "type": "refresh"
    })

    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decode and verify a JWT token.

    Args:
        token: The JWT token string

    Returns:
        Decoded payload if valid, None if invalid or expired
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


def verify_token(token: str, token_type: str = "access") -> Optional[Dict[str, Any]]:
    """
    Verify a token is valid and of the correct type.

    Args:
        token: The JWT token string
        token_type: Expected token type ('access' or 'refresh')

    Returns:
        Decoded payload if valid, None otherwise
    """
    payload = decode_token(token)

    if payload is None:
        return None

    if payload.get("type") != token_type:
        return None

    return payload


def create_preliminary_token(user_id: str) -> str:
    """
    Create a preliminary token for organisation selection.

    This token is used after login but before selecting an organisation.
    It has a short expiration (5 minutes) and limited permissions.

    Args:
        user_id: The user's ID

    Returns:
        Encoded JWT token string
    """
    token_data = {
        "sub": user_id,
        "type": "preliminary",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=5)
    }
    return jwt.encode(token_data, settings.SECRET_KEY, algorithm=ALGORITHM)


def verify_preliminary_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Verify a preliminary token for org selection.

    Args:
        token: The JWT token string

    Returns:
        Decoded payload if valid, None otherwise
    """
    payload = decode_token(token)

    if payload is None:
        return None

    if payload.get("type") != "preliminary":
        return None

    return payload


def create_tokens(user_id: str, org_id: str, role: str) -> Dict[str, Any]:
    """
    Create both access and refresh tokens for a user with an organisation context.

    Args:
        user_id: The user's ID
        org_id: The organisation ID
        role: The user's role in this organisation

    Returns:
        Dictionary with access_token, refresh_token, token_type, and expires_in
    """
    token_data = {
        "sub": user_id,
        "org_id": org_id,
        "role": role
    }

    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token({"sub": user_id, "org_id": org_id})

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "Bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60  # in seconds
    }
