"""
Organisation API Routes

Endpoints for organisation management, onboarding, and profile.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from typing import Optional

from app.core.database import get_db
from app.core.security import get_password_hash
from app.core.dependencies import get_current_user, get_current_org_membership, require_role, get_user_from_preliminary_token
from app.models.user import User, UserSettings, UserOrganisation
from app.models.organisation import Organisation
from app.schemas.organisation import (
    OrganisationOnboard,
    OrganisationResponse,
    OrganisationProfile,
    OrganisationStats,
    OnboardingResponse,
    OnboardingStatus,
    AddMemberRequest,
    AddMemberResponse,
    MemberResponse,
    OrganisationListItem,
)
from typing import List

router = APIRouter()


@router.post("/onboard", response_model=OnboardingResponse, status_code=status.HTTP_201_CREATED)
async def onboard_organisation(
    onboard_data: OrganisationOnboard,
    db: AsyncSession = Depends(get_db)
):
    """
    Complete organisation onboarding with initial configuration.

    This creates a new organisation and its admin user (or links existing user as admin).

    - **org_name**: Organisation display name
    - **org_slug**: URL-friendly identifier (lowercase, hyphens only)
    - **admin_email**: Email for the admin account
    - **admin_password**: Password for the admin account (ignored if user exists)
    - **admin_name**: Full name of the admin (ignored if user exists)
    - **branding**: Optional branding configuration
    - **settings**: Optional default settings
    """
    # Check if org_slug already exists
    result = await db.execute(select(Organisation).where(Organisation.org_slug == onboard_data.org_slug))
    existing_org = result.scalar_one_or_none()

    if existing_org:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Organisation slug already taken"
        )

    # Check if admin user already exists
    result = await db.execute(select(User).where(User.email == onboard_data.admin_email))
    existing_user = result.scalar_one_or_none()

    # Create organisation
    primary_color = "#3B82F6"
    if onboard_data.branding and onboard_data.branding.primary_color:
        primary_color = onboard_data.branding.primary_color

    new_org = Organisation(
        org_name=onboard_data.org_name,
        org_slug=onboard_data.org_slug,
        primary_color=primary_color,
        is_active=True,
    )

    db.add(new_org)
    await db.flush()  # Get the org_id

    if existing_user:
        # Link existing user as admin
        admin_user = existing_user
    else:
        # Create new admin user
        admin_user = User(
            email=onboard_data.admin_email,
            password_hash=get_password_hash(onboard_data.admin_password),
            full_name=onboard_data.admin_name,
            is_active=True,
            email_verified=True,  # Admin is auto-verified
        )
        db.add(admin_user)
        await db.flush()

        # Create admin user settings
        hotkey = "Ctrl+Shift+P"
        auto_capture = False
        if onboard_data.settings:
            hotkey = onboard_data.settings.hotkey
            auto_capture = onboard_data.settings.auto_capture_on_query

        admin_settings = UserSettings(
            user_id=admin_user.user_id,
            hotkey=hotkey,
            auto_capture_on_query=auto_capture,
        )
        db.add(admin_settings)

    # Create admin membership (link user to org)
    admin_membership = UserOrganisation(
        user_id=admin_user.user_id,
        org_id=new_org.org_id,
        role="org_admin",
        is_default=True,
    )
    db.add(admin_membership)

    # Create initial users if provided
    users_invited = 0
    if onboard_data.initial_users:
        for initial_user in onboard_data.initial_users:
            # Check if email already exists
            result = await db.execute(select(User).where(User.email == initial_user.email))
            existing = result.scalar_one_or_none()

            if existing:
                # Check if already member of this org
                result = await db.execute(
                    select(UserOrganisation).where(
                        UserOrganisation.user_id == existing.user_id,
                        UserOrganisation.org_id == new_org.org_id
                    )
                )
                if result.scalar_one_or_none():
                    continue  # Already a member

                # Add existing user to org
                membership = UserOrganisation(
                    user_id=existing.user_id,
                    org_id=new_org.org_id,
                    role=initial_user.role,
                )
                db.add(membership)
                users_invited += 1
            else:
                # Create placeholder user (would send invite email in production)
                new_user = User(
                    email=initial_user.email,
                    password_hash=get_password_hash("temp_password_change_me"),
                    is_active=False,  # Inactive until they accept invite
                    email_verified=False,
                )
                db.add(new_user)
                await db.flush()

                # Add to org
                membership = UserOrganisation(
                    user_id=new_user.user_id,
                    org_id=new_org.org_id,
                    role=initial_user.role,
                )
                db.add(membership)
                users_invited += 1

    await db.commit()
    await db.refresh(new_org)
    await db.refresh(admin_user)

    return OnboardingResponse(
        success=True,
        organisation=OrganisationResponse.model_validate(new_org),
        admin_user={
            "user_id": admin_user.user_id,
            "email": admin_user.email,
            "role": "org_admin",
        },
        users_invited=users_invited,
        next_steps=[
            "Login with your admin credentials",
            "Select this organisation after login",
            "Upload knowledge base documents via /org/upload-knowledge",
            "Invite additional users",
        ]
    )


@router.get("/profile", response_model=OrganisationProfile)
async def get_organisation_profile(
    current_user: User = Depends(get_current_user),
    membership: UserOrganisation = Depends(get_current_org_membership),
    db: AsyncSession = Depends(get_db)
):
    """
    Get the current organisation's profile.

    Returns full organisation details including branding, settings, and stats.
    """
    # Get organisation
    result = await db.execute(select(Organisation).where(Organisation.org_id == membership.org_id))
    organisation = result.scalar_one_or_none()

    if not organisation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organisation not found"
        )

    # Get member count
    result = await db.execute(
        select(func.count(UserOrganisation.id)).where(UserOrganisation.org_id == organisation.org_id)
    )
    total_users = result.scalar() or 0

    # Build response
    return OrganisationProfile(
        org_id=organisation.org_id,
        org_name=organisation.org_name,
        org_slug=organisation.org_slug,
        logo_path=organisation.logo_path,
        primary_color=organisation.primary_color,
        branding={
            "logo_path": organisation.logo_path,
            "primary_color": organisation.primary_color,
        },
        settings={
            "default_language": "en",
        },
        knowledge_bases=[],  # Populated in Phase 3
        stats=OrganisationStats(
            total_users=total_users,
            total_sessions=0,  # Populated when sessions are implemented
            last_activity=organisation.updated_at,
        )
    )


@router.get("/onboarding-status", response_model=OnboardingStatus)
async def get_onboarding_status(
    current_user: User = Depends(get_current_user),
    membership: UserOrganisation = Depends(get_current_org_membership),
    db: AsyncSession = Depends(get_db)
):
    """
    Check organisation onboarding progress.
    """
    # Get organisation
    result = await db.execute(select(Organisation).where(Organisation.org_id == membership.org_id))
    organisation = result.scalar_one_or_none()

    if not organisation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organisation not found"
        )

    # Check completion criteria
    checklist = {
        "organisation_configured": True,  # Always true at this point
        "logo_uploaded": organisation.logo_path is not None,
        "knowledge_base_uploaded": False,  # Check in Phase 3
        "first_user_invited": True,  # Admin exists
        "test_session_completed": False,  # Check when sessions implemented
    }

    completed = sum(1 for v in checklist.values() if v)
    total = len(checklist)
    percentage = int((completed / total) * 100)

    pending_items = []
    if not checklist["logo_uploaded"]:
        pending_items.append("Upload organisation logo")
    if not checklist["knowledge_base_uploaded"]:
        pending_items.append("Upload at least one knowledge base document")
    if not checklist["test_session_completed"]:
        pending_items.append("Complete a test guidance session")

    status_str = "completed" if percentage == 100 else "in_progress" if percentage > 0 else "pending"

    return OnboardingStatus(
        org_id=organisation.org_id,
        org_name=organisation.org_name,
        onboarding_status=status_str,
        checklist=checklist,
        completion_percentage=percentage,
        pending_items=pending_items,
    )


@router.put("/profile")
async def update_organisation_profile(
    primary_color: Optional[str] = None,
    org_name: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    membership: UserOrganisation = Depends(require_role(["org_admin"])),
    db: AsyncSession = Depends(get_db)
):
    """
    Update organisation profile (admin only).
    """
    result = await db.execute(select(Organisation).where(Organisation.org_id == membership.org_id))
    organisation = result.scalar_one_or_none()

    if not organisation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organisation not found"
        )

    if primary_color:
        organisation.primary_color = primary_color
    if org_name:
        organisation.org_name = org_name

    await db.commit()
    await db.refresh(organisation)

    return {
        "success": True,
        "message": "Organisation updated",
        "organisation": OrganisationResponse.model_validate(organisation)
    }


@router.get("/list", response_model=List[OrganisationListItem])
async def list_organisations(
    db: AsyncSession = Depends(get_db)
):
    """
    List all active organisations.

    This is a public endpoint that shows available organisations
    for users who want to join one.
    """
    result = await db.execute(
        select(Organisation).where(Organisation.is_active == True)
    )
    organisations = result.scalars().all()

    return [OrganisationListItem.model_validate(org) for org in organisations]


@router.post("/members", response_model=AddMemberResponse)
async def add_member(
    member_data: AddMemberRequest,
    current_user: User = Depends(get_current_user),
    membership: UserOrganisation = Depends(require_role(["org_admin", "manager"])),
    db: AsyncSession = Depends(get_db)
):
    """
    Add a user to the current organisation (admin/manager only).

    If the user exists, they are added to the org.
    If the user doesn't exist, returns an error (they must register first).

    - **email**: Email of the user to add
    - **role**: Role to assign (user, viewer, manager, org_admin)
    """
    # Find user by email
    result = await db.execute(select(User).where(User.email == member_data.email))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found. They must register first."
        )

    # Check if already a member
    result = await db.execute(
        select(UserOrganisation).where(
            UserOrganisation.user_id == user.user_id,
            UserOrganisation.org_id == membership.org_id
        )
    )
    existing_membership = result.scalar_one_or_none()

    if existing_membership:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User is already a member of this organisation"
        )

    # Add user to organisation
    new_membership = UserOrganisation(
        user_id=user.user_id,
        org_id=membership.org_id,
        role=member_data.role,
    )
    db.add(new_membership)
    await db.commit()
    await db.refresh(new_membership)

    return AddMemberResponse(
        success=True,
        message=f"User {user.email} added to organisation",
        member=MemberResponse(
            user_id=user.user_id,
            email=user.email,
            full_name=user.full_name,
            role=new_membership.role,
            joined_at=new_membership.joined_at,
        )
    )


@router.get("/members", response_model=List[MemberResponse])
async def list_members(
    current_user: User = Depends(get_current_user),
    membership: UserOrganisation = Depends(get_current_org_membership),
    db: AsyncSession = Depends(get_db)
):
    """
    List all members of the current organisation.
    """
    result = await db.execute(
        select(UserOrganisation)
        .options(selectinload(UserOrganisation.user))
        .where(UserOrganisation.org_id == membership.org_id)
    )
    memberships = result.scalars().all()

    return [
        MemberResponse(
            user_id=m.user.user_id,
            email=m.user.email,
            full_name=m.user.full_name,
            role=m.role,
            joined_at=m.joined_at,
        )
        for m in memberships
    ]


@router.delete("/members/{user_id}")
async def remove_member(
    user_id: str,
    current_user: User = Depends(get_current_user),
    membership: UserOrganisation = Depends(require_role(["org_admin"])),
    db: AsyncSession = Depends(get_db)
):
    """
    Remove a user from the organisation (admin only).
    """
    if user_id == current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove yourself from the organisation"
        )

    result = await db.execute(
        select(UserOrganisation).where(
            UserOrganisation.user_id == user_id,
            UserOrganisation.org_id == membership.org_id
        )
    )
    target_membership = result.scalar_one_or_none()

    if not target_membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User is not a member of this organisation"
        )

    await db.delete(target_membership)
    await db.commit()

    return {
        "success": True,
        "message": "User removed from organisation"
    }


@router.post("/join/{org_id}", response_model=AddMemberResponse)
async def join_organisation(
    org_id: str,
    current_user: User = Depends(get_user_from_preliminary_token),
    db: AsyncSession = Depends(get_db)
):
    """
    Join an organisation as a user.

    Any authenticated user can join any active organisation.
    They will be added with the 'user' role by default.

    - **org_id**: The organisation ID to join
    """
    # Check if organisation exists and is active
    result = await db.execute(
        select(Organisation).where(
            Organisation.org_id == org_id,
            Organisation.is_active == True
        )
    )
    organisation = result.scalar_one_or_none()

    if not organisation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organisation not found or is not active"
        )

    # Check if already a member
    result = await db.execute(
        select(UserOrganisation).where(
            UserOrganisation.user_id == current_user.user_id,
            UserOrganisation.org_id == org_id
        )
    )
    existing_membership = result.scalar_one_or_none()

    if existing_membership:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You are already a member of this organisation"
        )

    # Add user to organisation with 'user' role
    new_membership = UserOrganisation(
        user_id=current_user.user_id,
        org_id=org_id,
        role="user",
    )
    db.add(new_membership)
    await db.commit()
    await db.refresh(new_membership)

    return AddMemberResponse(
        success=True,
        message=f"Successfully joined {organisation.org_name}",
        member=MemberResponse(
            user_id=current_user.user_id,
            email=current_user.email,
            full_name=current_user.full_name,
            role=new_membership.role,
            joined_at=new_membership.joined_at,
        )
    )
