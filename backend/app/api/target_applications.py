"""
Target Applications API Routes

Endpoints for managing multiple target applications per organisation.
Each organisation can have multiple target apps (websites, desktop apps, etc.)
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional

from app.core.database import get_db
from app.core.dependencies import get_current_user, get_current_org_membership, require_role
from app.models.user import User, UserOrganisation
from app.models.target_application import TargetApplication
from app.schemas.target_application import (
    TargetAppCreate,
    TargetAppUpdate,
    TargetAppResponse,
    TargetAppListResponse,
    TargetAppDeleteResponse,
    SetDefaultResponse,
)

router = APIRouter()


def _build_response(app: TargetApplication) -> TargetAppResponse:
    """Build a TargetAppResponse from a TargetApplication model."""
    return TargetAppResponse(
        app_id=app.app_id,
        org_id=app.org_id,
        app_name=app.app_name,
        description=app.description,
        match_mode=app.match_mode,
        url_pattern=app.url_pattern,
        url_patterns=app.url_patterns,
        process_name=app.process_name,
        brand_keywords=app.brand_keywords,
        window_pattern=app.window_pattern,
        window_class=app.window_class,
        app_config=app.app_config,
        is_active=app.is_active,
        is_default=app.is_default,
        is_configured=app.is_configured,
        created_at=app.created_at,
        updated_at=app.updated_at,
    )


# ============================================
# Target Application CRUD
# ============================================

@router.get("", response_model=TargetAppListResponse)
async def list_target_apps(
    active_only: bool = False,
    membership: UserOrganisation = Depends(get_current_org_membership),
    db: AsyncSession = Depends(get_db)
):
    """
    List all target applications for the current organisation.

    - **active_only**: If true, only return active target apps
    """
    query = select(TargetApplication).where(
        TargetApplication.org_id == membership.org_id
    )

    if active_only:
        query = query.where(TargetApplication.is_active == True)

    query = query.order_by(
        TargetApplication.is_default.desc(),
        TargetApplication.app_name
    )

    result = await db.execute(query)
    apps = result.scalars().all()

    return TargetAppListResponse(
        target_apps=[_build_response(app) for app in apps],
        total_count=len(apps)
    )


@router.get("/default", response_model=Optional[TargetAppResponse])
async def get_default_target_app(
    membership: UserOrganisation = Depends(get_current_org_membership),
    db: AsyncSession = Depends(get_db)
):
    """
    Get the default target application for the organisation.

    Returns null if no default is set.
    """
    result = await db.execute(
        select(TargetApplication).where(
            TargetApplication.org_id == membership.org_id,
            TargetApplication.is_default == True,
            TargetApplication.is_active == True
        )
    )
    app = result.scalar_one_or_none()

    if not app:
        return None

    return _build_response(app)


@router.get("/{app_id}", response_model=TargetAppResponse)
async def get_target_app(
    app_id: str,
    membership: UserOrganisation = Depends(get_current_org_membership),
    db: AsyncSession = Depends(get_db)
):
    """
    Get a specific target application by ID.

    - **app_id**: Target application ID
    """
    result = await db.execute(
        select(TargetApplication).where(
            TargetApplication.app_id == app_id,
            TargetApplication.org_id == membership.org_id
        )
    )
    app = result.scalar_one_or_none()

    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target application not found"
        )

    return _build_response(app)


@router.post("", response_model=TargetAppResponse, status_code=status.HTTP_201_CREATED)
async def create_target_app(
    app_data: TargetAppCreate,
    membership: UserOrganisation = Depends(require_role(["org_admin", "manager"])),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new target application.

    Requires org_admin or manager role.

    - **app_name**: Name of the target application
    - **description**: Optional description
    - **match_mode**: How to match the window ('url', 'process', 'title', 'auto')
    - **url_pattern**: URL pattern for websites
    - **url_patterns**: Array of URL patterns for multi-domain sites
    - **process_name**: Process executable name for desktop apps
    - **window_pattern**: Window title pattern (legacy fallback)
    - **is_default**: Set as default target app
    """
    # If this is set as default, unset existing default
    if app_data.is_default:
        await _clear_default(membership.org_id, db)

    # Create the new target app
    new_app = TargetApplication(
        org_id=membership.org_id,
        app_name=app_data.app_name,
        description=app_data.description,
        match_mode=app_data.match_mode,
        url_pattern=app_data.url_pattern,
        url_patterns=app_data.url_patterns,
        process_name=app_data.process_name,
        brand_keywords=app_data.brand_keywords,
        window_pattern=app_data.window_pattern,
        window_class=app_data.window_class,
        app_config=app_data.app_config,
        is_active=app_data.is_active,
        is_default=app_data.is_default,
    )

    db.add(new_app)
    await db.commit()
    await db.refresh(new_app)

    return _build_response(new_app)


@router.put("/{app_id}", response_model=TargetAppResponse)
async def update_target_app(
    app_id: str,
    app_update: TargetAppUpdate,
    membership: UserOrganisation = Depends(require_role(["org_admin", "manager"])),
    db: AsyncSession = Depends(get_db)
):
    """
    Update a target application.

    Requires org_admin or manager role.

    - **app_id**: Target application ID
    """
    result = await db.execute(
        select(TargetApplication).where(
            TargetApplication.app_id == app_id,
            TargetApplication.org_id == membership.org_id
        )
    )
    app = result.scalar_one_or_none()

    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target application not found"
        )

    # Update fields if provided
    update_data = app_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(app, field, value)

    await db.commit()
    await db.refresh(app)

    return _build_response(app)


@router.delete("/{app_id}", response_model=TargetAppDeleteResponse)
async def delete_target_app(
    app_id: str,
    membership: UserOrganisation = Depends(require_role(["org_admin"])),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a target application.

    Requires org_admin role. This action is irreversible.

    - **app_id**: Target application ID to delete
    """
    result = await db.execute(
        select(TargetApplication).where(
            TargetApplication.app_id == app_id,
            TargetApplication.org_id == membership.org_id
        )
    )
    app = result.scalar_one_or_none()

    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target application not found"
        )

    await db.delete(app)
    await db.commit()

    return TargetAppDeleteResponse(
        success=True,
        message=f"Target application '{app.app_name}' deleted",
        app_id=app_id
    )


@router.put("/{app_id}/default", response_model=SetDefaultResponse)
async def set_default_target_app(
    app_id: str,
    membership: UserOrganisation = Depends(require_role(["org_admin", "manager"])),
    db: AsyncSession = Depends(get_db)
):
    """
    Set a target application as the default.

    Only one app per organisation can be the default.
    The previous default (if any) will be unset.

    Requires org_admin or manager role.

    - **app_id**: Target application ID to set as default
    """
    # Get the target app
    result = await db.execute(
        select(TargetApplication).where(
            TargetApplication.app_id == app_id,
            TargetApplication.org_id == membership.org_id
        )
    )
    app = result.scalar_one_or_none()

    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target application not found"
        )

    # Get current default (if any)
    result = await db.execute(
        select(TargetApplication).where(
            TargetApplication.org_id == membership.org_id,
            TargetApplication.is_default == True
        )
    )
    previous_default = result.scalar_one_or_none()
    previous_default_id = previous_default.app_id if previous_default else None

    # Clear all defaults for this org
    await _clear_default(membership.org_id, db)

    # Set the new default
    app.is_default = True
    await db.commit()
    await db.refresh(app)

    return SetDefaultResponse(
        success=True,
        message=f"'{app.app_name}' is now the default target application",
        app_id=app_id,
        previous_default_id=previous_default_id
    )


@router.put("/{app_id}/toggle-active", response_model=TargetAppResponse)
async def toggle_target_app_active(
    app_id: str,
    membership: UserOrganisation = Depends(require_role(["org_admin", "manager"])),
    db: AsyncSession = Depends(get_db)
):
    """
    Toggle the active status of a target application.

    Requires org_admin or manager role.

    - **app_id**: Target application ID
    """
    result = await db.execute(
        select(TargetApplication).where(
            TargetApplication.app_id == app_id,
            TargetApplication.org_id == membership.org_id
        )
    )
    app = result.scalar_one_or_none()

    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target application not found"
        )

    app.is_active = not app.is_active
    await db.commit()
    await db.refresh(app)

    return _build_response(app)


# ============================================
# Helper Functions
# ============================================

async def _clear_default(org_id: str, db: AsyncSession):
    """Clear the default flag for all target apps in an organisation."""
    result = await db.execute(
        select(TargetApplication).where(
            TargetApplication.org_id == org_id,
            TargetApplication.is_default == True
        )
    )
    apps = result.scalars().all()

    for app in apps:
        app.is_default = False
