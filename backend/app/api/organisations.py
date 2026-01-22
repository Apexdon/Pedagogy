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
    OrgDashboardStats,
    TeamMemberSummary,
    KnowledgeBaseSummary,
    RecentActivityItem,
    UpdateTargetAppRequest,
    TargetAppResponse,
    UpdateTargetAppResponse,
    WindowInfo,
    DetectWindowsResponse,
    ValidatePatternRequest,
    ValidatePatternResponse,
)
from app.models.knowledge import KnowledgeBase, Document, DocumentChunk
from app.models.target_application import TargetApplication
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


@router.get("/dashboard", response_model=OrgDashboardStats)
async def get_org_dashboard_stats(
    current_user: User = Depends(get_current_user),
    membership: UserOrganisation = Depends(require_role(["org_admin", "manager"])),
    db: AsyncSession = Depends(get_db)
):
    """
    Get comprehensive dashboard statistics for org admin/manager.

    Returns overview stats, team members, knowledge base summary,
    and recent activity for the organisation dashboard.
    """
    org_id = membership.org_id

    # Get organisation
    result = await db.execute(select(Organisation).where(Organisation.org_id == org_id))
    organisation = result.scalar_one_or_none()

    if not organisation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organisation not found"
        )

    # Get total members count
    result = await db.execute(
        select(func.count(UserOrganisation.id)).where(UserOrganisation.org_id == org_id)
    )
    total_members = result.scalar() or 0

    # Get members by role
    result = await db.execute(
        select(UserOrganisation.role, func.count(UserOrganisation.id))
        .where(UserOrganisation.org_id == org_id)
        .group_by(UserOrganisation.role)
    )
    role_counts = {role: count for role, count in result.all()}

    # Get team members (latest 10)
    result = await db.execute(
        select(UserOrganisation)
        .options(selectinload(UserOrganisation.user))
        .where(UserOrganisation.org_id == org_id)
        .order_by(UserOrganisation.joined_at.desc())
        .limit(10)
    )
    memberships = result.scalars().all()

    team_members = [
        TeamMemberSummary(
            user_id=m.user.user_id,
            full_name=m.user.full_name,
            email=m.user.email,
            role=m.role,
            joined_at=m.joined_at,
        )
        for m in memberships
    ]

    # Get knowledge base stats
    result = await db.execute(
        select(func.count(KnowledgeBase.kb_id)).where(KnowledgeBase.org_id == org_id)
    )
    total_knowledge_bases = result.scalar() or 0

    # Get document stats
    result = await db.execute(
        select(func.count(Document.doc_id))
        .join(KnowledgeBase, Document.kb_id == KnowledgeBase.kb_id)
        .where(KnowledgeBase.org_id == org_id)
    )
    total_documents = result.scalar() or 0

    # Get chunk stats
    result = await db.execute(
        select(func.count(DocumentChunk.chunk_id))
        .join(Document, DocumentChunk.doc_id == Document.doc_id)
        .join(KnowledgeBase, Document.kb_id == KnowledgeBase.kb_id)
        .where(KnowledgeBase.org_id == org_id)
    )
    total_chunks = result.scalar() or 0

    # Get document processing status counts
    result = await db.execute(
        select(Document.status, func.count(Document.doc_id))
        .join(KnowledgeBase, Document.kb_id == KnowledgeBase.kb_id)
        .where(KnowledgeBase.org_id == org_id)
        .group_by(Document.status)
    )
    processing_status = {status: count for status, count in result.all()}

    # Get recent document uploads (last 5)
    result = await db.execute(
        select(Document)
        .join(KnowledgeBase, Document.kb_id == KnowledgeBase.kb_id)
        .where(KnowledgeBase.org_id == org_id)
        .order_by(Document.uploaded_at.desc())
        .limit(5)
    )
    recent_docs = result.scalars().all()
    recent_uploads = [
        {
            "doc_id": doc.doc_id,
            "doc_name": doc.doc_name,
            "doc_type": doc.doc_type,
            "status": doc.status,
            "uploaded_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None,
        }
        for doc in recent_docs
    ]

    # Calculate onboarding completion
    checklist = {
        "organisation_configured": True,
        "logo_uploaded": organisation.logo_path is not None,
        "knowledge_base_uploaded": total_documents > 0,
        "first_user_invited": total_members > 1,
        "test_session_completed": False,  # TODO: implement when sessions exist
    }
    completed = sum(1 for v in checklist.values() if v)
    onboarding_completion = int((completed / len(checklist)) * 100)

    pending_setup_items = []
    if not checklist["logo_uploaded"]:
        pending_setup_items.append("Upload organisation logo")
    if not checklist["knowledge_base_uploaded"]:
        pending_setup_items.append("Upload knowledge base documents")
    if not checklist["first_user_invited"]:
        pending_setup_items.append("Invite team members")
    if not checklist["test_session_completed"]:
        pending_setup_items.append("Complete a test guidance session")

    # Build recent activities (combine member joins and document uploads)
    activities = []

    # Add member join activities
    for m in memberships[:5]:
        activities.append(
            RecentActivityItem(
                activity_id=f"member_{m.user.user_id}",
                activity_type="member_joined",
                description=f"{m.user.full_name or m.user.email} joined the organisation",
                timestamp=m.joined_at,
                user_name=m.user.full_name or m.user.email,
                metadata={"role": m.role},
            )
        )

    # Add document upload activities
    for doc in recent_docs:
        activities.append(
            RecentActivityItem(
                activity_id=f"doc_{doc.doc_id}",
                activity_type="document_uploaded",
                description=f"Document '{doc.doc_name}' was uploaded",
                timestamp=doc.uploaded_at,
                metadata={"doc_type": doc.doc_type, "status": doc.status},
            )
        )

    # Sort activities by timestamp and take top 10
    activities.sort(key=lambda x: x.timestamp, reverse=True)
    recent_activities = activities[:10]

    return OrgDashboardStats(
        total_members=total_members,
        total_documents=total_documents,
        total_sessions=0,  # TODO: implement when sessions exist
        total_knowledge_bases=total_knowledge_bases,
        onboarding_completion=onboarding_completion,
        pending_setup_items=pending_setup_items,
        recent_activities=recent_activities,
        team_members=team_members,
        members_by_role=role_counts,
        knowledge_base=KnowledgeBaseSummary(
            total_documents=total_documents,
            total_chunks=total_chunks,
            recent_uploads=recent_uploads,
            processing_status=processing_status,
        ),
        sessions_this_week=0,
        sessions_trend="stable",
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


# =============================================
# Target Application Settings Endpoints (Legacy)
# These endpoints now use the TargetApplication model
# for backwards compatibility with existing frontend code.
# New code should use /target-apps endpoints instead.
# =============================================

@router.get("/target-app", response_model=TargetAppResponse)
async def get_target_app_settings(
    current_user: User = Depends(get_current_user),
    membership: UserOrganisation = Depends(get_current_org_membership),
    db: AsyncSession = Depends(get_db)
):
    """
    Get target application settings for the current organisation.

    Returns the default target application's settings.
    For multi-app support, use /target-apps endpoints.
    """
    # Get the default target app from the new model
    result = await db.execute(
        select(TargetApplication).where(
            TargetApplication.org_id == membership.org_id,
            TargetApplication.is_default == True,
            TargetApplication.is_active == True
        )
    )
    target_app = result.scalar_one_or_none()

    # If no default, try to get the first active app
    if not target_app:
        result = await db.execute(
            select(TargetApplication).where(
                TargetApplication.org_id == membership.org_id,
                TargetApplication.is_active == True
            ).order_by(TargetApplication.created_at)
        )
        target_app = result.scalars().first()

    # Build response from target app or return empty config
    if target_app:
        return TargetAppResponse(
            org_id=membership.org_id,
            target_app_name=target_app.app_name,
            target_window_pattern=target_app.window_pattern,
            target_process_name=target_app.process_name,
            target_window_class=target_app.window_class,
            target_app_config=target_app.app_config,
            target_match_mode=target_app.match_mode or "auto",
            target_url_pattern=target_app.url_pattern,
            target_url_patterns=target_app.url_patterns,
            target_brand_keywords=target_app.brand_keywords,
            is_configured=target_app.is_configured,
        )
    else:
        return TargetAppResponse(
            org_id=membership.org_id,
            is_configured=False,
        )


@router.put("/target-app", response_model=UpdateTargetAppResponse)
async def update_target_app_settings(
    request: UpdateTargetAppRequest,
    current_user: User = Depends(get_current_user),
    membership: UserOrganisation = Depends(require_role(["org_admin", "manager"])),
    db: AsyncSession = Depends(get_db)
):
    """
    Update target application settings for the organisation.

    Creates or updates the default target application.
    For multi-app support, use /target-apps endpoints.
    """
    # Get the default target app
    result = await db.execute(
        select(TargetApplication).where(
            TargetApplication.org_id == membership.org_id,
            TargetApplication.is_default == True
        )
    )
    target_app = result.scalar_one_or_none()

    if not target_app:
        # Create a new default target app
        target_app = TargetApplication(
            org_id=membership.org_id,
            app_name=request.target_app_name or "Default App",
            is_default=True,
            is_active=True,
        )
        db.add(target_app)

    # Update fields if provided
    if request.target_app_name is not None:
        target_app.app_name = request.target_app_name
    if request.target_window_pattern is not None:
        target_app.window_pattern = request.target_window_pattern
    if request.target_process_name is not None:
        target_app.process_name = request.target_process_name
    if request.target_window_class is not None:
        target_app.window_class = request.target_window_class
    if request.target_app_config is not None:
        target_app.app_config = request.target_app_config
    # Smart matching fields
    if request.target_match_mode is not None:
        target_app.match_mode = request.target_match_mode
    if request.target_url_pattern is not None:
        target_app.url_pattern = request.target_url_pattern
    if request.target_url_patterns is not None:
        target_app.url_patterns = request.target_url_patterns

    await db.commit()
    await db.refresh(target_app)

    return UpdateTargetAppResponse(
        success=True,
        message="Target application settings updated",
        target_app=TargetAppResponse(
            org_id=membership.org_id,
            target_app_name=target_app.app_name,
            target_window_pattern=target_app.window_pattern,
            target_process_name=target_app.process_name,
            target_window_class=target_app.window_class,
            target_app_config=target_app.app_config,
            target_match_mode=target_app.match_mode or "auto",
            target_url_pattern=target_app.url_pattern,
            target_url_patterns=target_app.url_patterns,
            target_brand_keywords=target_app.brand_keywords,
            is_configured=target_app.is_configured,
        )
    )


@router.delete("/target-app")
async def clear_target_app_settings(
    current_user: User = Depends(get_current_user),
    membership: UserOrganisation = Depends(require_role(["org_admin"])),
    db: AsyncSession = Depends(get_db)
):
    """
    Clear target application settings (admin only).

    Deactivates the default target app.
    For multi-app support, use /target-apps endpoints.
    """
    # Get the default target app
    result = await db.execute(
        select(TargetApplication).where(
            TargetApplication.org_id == membership.org_id,
            TargetApplication.is_default == True
        )
    )
    target_app = result.scalar_one_or_none()

    if target_app:
        # Deactivate instead of delete for data preservation
        target_app.is_active = False
        await db.commit()

    return {
        "success": True,
        "message": "Target application settings cleared"
    }


@router.get("/windows", response_model=DetectWindowsResponse)
async def detect_windows(
    current_user: User = Depends(get_current_user),
    membership: UserOrganisation = Depends(get_current_org_membership),
    db: AsyncSession = Depends(get_db)
):
    """
    Detect all visible windows on the user's system.

    Returns a list of windows that can be used to configure the target app.
    If the organisation has a window pattern configured, also shows which
    window matches.

    Note: This requires the desktop client to be running.
    """
    from app.services.window_capture import get_window_capture_service

    # Get organisation for pattern matching
    result = await db.execute(
        select(Organisation).where(Organisation.org_id == membership.org_id)
    )
    organisation = result.scalar_one_or_none()

    window_service = get_window_capture_service()
    windows = window_service.list_windows(visible_only=True)

    # Convert to response format
    window_list = [
        WindowInfo(
            window_handle=w.window_handle,
            title=w.title,
            process_name=w.process_name,
            process_id=w.process_id,
            is_visible=w.is_visible,
            is_minimized=w.is_minimized,
            rect=w.rect,
        )
        for w in windows
    ]

    # Find matching window if pattern is configured
    matching_window = None
    if organisation and organisation.target_window_pattern:
        match = window_service.find_window_by_pattern(
            organisation.target_window_pattern,
            organisation.target_process_name
        )
        if match:
            matching_window = WindowInfo(
                window_handle=match.window_handle,
                title=match.title,
                process_name=match.process_name,
                process_id=match.process_id,
                is_visible=match.is_visible,
                is_minimized=match.is_minimized,
                rect=match.rect,
            )

    return DetectWindowsResponse(
        windows=window_list,
        total=len(window_list),
        matching_window=matching_window,
    )


@router.post("/validate-pattern", response_model=ValidatePatternResponse)
async def validate_window_pattern(
    request: ValidatePatternRequest,
    current_user: User = Depends(get_current_user),
    membership: UserOrganisation = Depends(get_current_org_membership),
):
    """
    Validate a window pattern by checking if any windows match.

    Use this to test patterns before saving them.

    - **pattern**: Window title pattern to validate (supports wildcards)
    """
    from app.services.window_capture import get_window_capture_service

    window_service = get_window_capture_service()
    is_valid, matching, error = window_service.validate_pattern(request.pattern)

    matching_windows = [
        WindowInfo(
            window_handle=w.window_handle,
            title=w.title,
            process_name=w.process_name,
            process_id=w.process_id,
            is_visible=w.is_visible,
            is_minimized=w.is_minimized,
            rect=w.rect,
        )
        for w in matching
    ]

    return ValidatePatternResponse(
        pattern=request.pattern,
        is_valid=is_valid,
        matching_windows=matching_windows,
        error_message=error,
    )
