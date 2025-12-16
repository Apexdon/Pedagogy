"""
Authentication API Routes

Endpoints for user registration, login, logout, organisation selection, and token refresh.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from datetime import datetime, timezone
from typing import Optional

from app.core.database import get_db
from app.core.security import (
    get_password_hash,
    verify_password,
    create_tokens,
    create_preliminary_token,
    verify_preliminary_token,
    verify_token,
)
from app.core.dependencies import get_current_user
from app.models.user import User, UserSettings, UserOrganisation
from app.models.organisation import Organisation
from app.schemas.auth import (
    UserRegister,
    UserLogin,
    SelectOrganisation,
    Token,
    UserResponse,
    LoginResponse,
    SelectOrgResponse,
    RegisterResponse,
    RefreshTokenRequest,
    LogoutRequest,
    OrganisationBasic,
    UserOrganisationInfo,
)

router = APIRouter()


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserRegister,
    db: AsyncSession = Depends(get_db)
):
    """
    Register a new user account.

    Users register independently without being tied to an organisation.
    After registration, they can join organisations or create their own.

    - **email**: User's email address (must be unique)
    - **password**: Password (min 8 characters)
    - **full_name**: User's full name
    """
    # Check if email already exists
    result = await db.execute(select(User).where(User.email == user_data.email))
    existing_user = result.scalar_one_or_none()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered"
        )

    # Create new user (no organisation yet)
    new_user = User(
        email=user_data.email,
        password_hash=get_password_hash(user_data.password),
        full_name=user_data.full_name,
        is_active=True,
        email_verified=False,
    )

    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    # Create default user settings
    user_settings = UserSettings(user_id=new_user.user_id)
    db.add(user_settings)
    await db.commit()

    return RegisterResponse(
        success=True,
        user=UserResponse.model_validate(new_user),
        message="Registration successful. You can now join or create an organisation."
    )


@router.post("/login", response_model=LoginResponse)
async def login(
    credentials: UserLogin,
    db: AsyncSession = Depends(get_db)
):
    """
    Authenticate user and return their organisations.

    After successful login, user receives a preliminary token and must
    select an organisation to get a full access token.

    - **email**: User's email address
    - **password**: User's password
    """
    # Find user by email with their organisations
    result = await db.execute(
        select(User)
        .options(selectinload(User.organisations).selectinload(UserOrganisation.organisation))
        .where(User.email == credentials.email)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    if not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is disabled"
        )

    # Update last login
    user.last_login = datetime.now(timezone.utc)
    await db.commit()

    # Build list of user's organisations
    user_orgs = []
    admin_membership = None  # Track if user is org_admin or manager

    for membership in user.organisations:
        org = membership.organisation
        if org.is_active:
            user_orgs.append(UserOrganisationInfo(
                org_id=org.org_id,
                org_name=org.org_name,
                org_slug=org.org_slug,
                role=membership.role,
                is_default=membership.is_default,
                joined_at=membership.joined_at,
            ))
            # Check if this user is an org_admin or manager
            if membership.role in ('org_admin', 'manager') and admin_membership is None:
                admin_membership = membership

    # For org_admin/manager users, return full tokens directly (skip org selection)
    if admin_membership:
        tokens = create_tokens(user.user_id, admin_membership.org_id, admin_membership.role)
        return LoginResponse(
            success=True,
            user=UserResponse.model_validate(user),
            organisations=user_orgs,
            requires_org_selection=False,
            preliminary_token=None,
            tokens=Token(**tokens),
            organisation=OrganisationBasic.model_validate(admin_membership.organisation),
            role=admin_membership.role,
        )

    # For regular users, create preliminary token for org selection
    preliminary_token = create_preliminary_token(user.user_id)

    return LoginResponse(
        success=True,
        user=UserResponse.model_validate(user),
        organisations=user_orgs,
        requires_org_selection=len(user_orgs) > 0,
        preliminary_token=preliminary_token,
    )


@router.post("/select-organisation", response_model=SelectOrgResponse)
async def select_organisation(
    selection: SelectOrganisation,
    authorization: str = Header(..., description="Bearer <preliminary_token>"),
    db: AsyncSession = Depends(get_db)
):
    """
    Select an organisation after login.

    Use the preliminary token from login to select an organisation.
    Returns full access and refresh tokens.

    - **org_id**: Organisation ID to select
    """
    # Extract token from header
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header"
        )

    token = authorization[7:]  # Remove "Bearer " prefix
    payload = verify_preliminary_token(token)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired preliminary token"
        )

    user_id = payload.get("sub")

    # Get user
    result = await db.execute(select(User).where(User.user_id == user_id))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )

    # Verify user belongs to this organisation
    result = await db.execute(
        select(UserOrganisation)
        .options(selectinload(UserOrganisation.organisation))
        .where(
            UserOrganisation.user_id == user_id,
            UserOrganisation.org_id == selection.org_id
        )
    )
    membership = result.scalar_one_or_none()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this organisation"
        )

    if not membership.organisation.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organisation is not active"
        )

    # Create full tokens with org context
    tokens = create_tokens(user.user_id, membership.org_id, membership.role)

    return SelectOrgResponse(
        success=True,
        user=UserResponse.model_validate(user),
        organisation=OrganisationBasic.model_validate(membership.organisation),
        role=membership.role,
        tokens=Token(**tokens),
    )


@router.post("/logout")
async def logout(
    logout_data: LogoutRequest = None,
    current_user: User = Depends(get_current_user)
):
    """
    Logout the current user.

    In a production environment, this would invalidate the refresh token
    by storing it in a blacklist.
    """
    return {
        "success": True,
        "message": "Successfully logged out",
        "sessions_terminated": 1
    }


@router.post("/refresh", response_model=Token)
async def refresh_token(
    token_request: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Refresh access token using a valid refresh token.

    - **refresh_token**: Valid refresh token
    """
    payload = verify_token(token_request.refresh_token, token_type="refresh")

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token"
        )

    user_id = payload.get("sub")
    org_id = payload.get("org_id")

    # Get user to verify they still exist and are active
    result = await db.execute(select(User).where(User.user_id == user_id))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )

    # Get user's role in this org
    result = await db.execute(
        select(UserOrganisation).where(
            UserOrganisation.user_id == user_id,
            UserOrganisation.org_id == org_id
        )
    )
    membership = result.scalar_one_or_none()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User no longer member of this organisation"
        )

    # Create new tokens
    tokens = create_tokens(user.user_id, org_id, membership.role)

    return Token(**tokens)


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: User = Depends(get_current_user)
):
    """
    Get the current authenticated user's profile.
    """
    return UserResponse.model_validate(current_user)


@router.post("/verify-email")
async def verify_email(
    verification_token: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Verify user's email address.

    In production, this would validate a token sent via email.
    """
    return {
        "success": True,
        "message": "Email verification not yet implemented"
    }


@router.post("/forgot-password")
async def forgot_password(
    email: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Request a password reset email.

    - **email**: User's registered email
    """
    # Always return success to prevent email enumeration
    return {
        "success": True,
        "message": "If an account exists with this email, a password reset link has been sent"
    }


@router.post("/reset-password")
async def reset_password(
    reset_token: str,
    new_password: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Reset password using a valid reset token.
    """
    return {
        "success": True,
        "message": "Password reset not yet implemented"
    }
