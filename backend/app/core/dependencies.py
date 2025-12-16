"""
Dependencies Module

FastAPI dependencies for authentication and authorization.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, List

from app.core.database import get_db
from app.core.security import verify_token, verify_preliminary_token
from app.models.user import User, UserOrganisation

# HTTP Bearer token security
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Dependency to get the current authenticated user.

    Raises:
        HTTPException 401: If token is invalid or user not found
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token = credentials.credentials
    payload = verify_token(token, token_type="access")

    if payload is None:
        raise credentials_exception

    user_id = payload.get("sub")
    if user_id is None:
        raise credentials_exception

    # Get user from database
    result = await db.execute(select(User).where(User.user_id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is disabled"
        )

    return user


async def get_current_org_membership(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> UserOrganisation:
    """
    Dependency to get the current user's organisation membership from the token.

    The token contains org_id and role for the selected organisation.

    Raises:
        HTTPException 401: If token is invalid or doesn't contain org context
        HTTPException 403: If user is not a member of the organisation
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token = credentials.credentials
    payload = verify_token(token, token_type="access")

    if payload is None:
        raise credentials_exception

    user_id = payload.get("sub")
    org_id = payload.get("org_id")

    if user_id is None:
        raise credentials_exception

    if org_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No organisation selected. Please select an organisation first."
        )

    # Get the membership
    result = await db.execute(
        select(UserOrganisation).where(
            UserOrganisation.user_id == user_id,
            UserOrganisation.org_id == org_id
        )
    )
    membership = result.scalar_one_or_none()

    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this organisation"
        )

    return membership


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Dependency to get the current active user.
    Ensures the user account is active.
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    return current_user


def require_role(allowed_roles: List[str]):
    """
    Dependency factory to require specific roles within the current organisation.

    Usage:
        @router.get("/admin")
        async def admin_endpoint(membership = Depends(require_role(["org_admin"]))):
            ...
    """
    async def role_checker(
        membership: UserOrganisation = Depends(get_current_org_membership)
    ) -> UserOrganisation:
        if membership.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
        return membership

    return role_checker


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    db: AsyncSession = Depends(get_db)
) -> Optional[User]:
    """
    Dependency to optionally get the current user.
    Returns None if no valid token provided (doesn't raise exception).
    """
    if credentials is None:
        return None

    token = credentials.credentials
    payload = verify_token(token, token_type="access")

    if payload is None:
        return None

    user_id = payload.get("sub")
    if user_id is None:
        return None

    result = await db.execute(select(User).where(User.user_id == user_id))
    user = result.scalar_one_or_none()

    return user if user and user.is_active else None


async def get_user_from_preliminary_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Dependency to get the current user from a preliminary token.

    This is used for endpoints that should work BEFORE org selection,
    such as joining an organisation.

    Raises:
        HTTPException 401: If token is invalid or user not found
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token = credentials.credentials
    payload = verify_preliminary_token(token)

    if payload is None:
        raise credentials_exception

    user_id = payload.get("sub")
    if user_id is None:
        raise credentials_exception

    # Get user from database
    result = await db.execute(select(User).where(User.user_id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is disabled"
        )

    return user
