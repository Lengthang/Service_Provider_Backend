from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from core.enums import ProviderStatus, UserRole
from db.database import get_db
from models.booking import Booking
from models.provider import ProviderProfile
from models.user import User
from schemas.booking import BookingResponse
from schemas.user import UserResponse, UserDetailResponse
from schemas.provider import ProviderResponse, ApprovalRequest
from services.provider_service import register_provider
from core.dependencies import get_current_user, get_admin_user
from datetime import datetime, timezone
from typing import List
from enum import Enum
from sqlalchemy.orm import joinedload, selectinload
from api.routes.bookings import booking_with_relations, serialize_booking
from sqlalchemy.orm import selectinload

router = APIRouter(prefix="/admin", tags=["Admin"])

# --- Admin: view all bookings ---
@router.get("/bookings", response_model=List[BookingResponse])
async def get_all_bookings(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Booking)
        .options(*booking_with_relations())
        .order_by(Booking.created_at.desc())
    )
    bookings = result.scalars().all()
    return [serialize_booking(b) for b in bookings]
# --- Get all user, By Admin ---
@router.get("/users", response_model=List[UserResponse])
async def get_all_user(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User))
    users = result.scalars().all()

    return users

# --- Get specific role profile ---
@router.get("/role", response_model=List[UserDetailResponse])
async def get_users_by_role(
    role: UserRole,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(User)
        .where(User.role == role.value)
        .options(
            joinedload(User.provider_profile).selectinload(ProviderProfile.availability),
            joinedload(User.provider_profile).selectinload(ProviderProfile.services),
            joinedload(User.provider_profile).selectinload(ProviderProfile.categories),  # ← ADD
        )
    )
    users = result.unique().scalars().all()  # ← also add .unique() (see note below)

    if not users:
        raise HTTPException(status_code=404, detail="No users found for this role")

    return users



# --- get all pending providers ---
@router.get("/pending", response_model=List[ProviderResponse])
async def get_pending_providers(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(ProviderProfile)
        .where(ProviderProfile.status == 'pending')
        .options(
            selectinload(ProviderProfile.categories),
            selectinload(ProviderProfile.availability),
        )
    )
    return result.scalars().all()

# --- get a detail user show full detail ---
@router.get("/providers/{user_id}", response_model=UserDetailResponse)
async def get_user_detail(
    user_id :str,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
   
    result = await db.execute(
        select(User).where(User.id == user_id)
        .options(
            joinedload(User.provider_profile).selectinload(ProviderProfile.availability),
            joinedload(User.provider_profile).selectinload(ProviderProfile.services),
            joinedload(User.provider_profile).selectinload(ProviderProfile.categories),
        )
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User ID not found")

    return user
# --- approve or reject a provider ---
@router.patch("/{provider_id}/approval", response_model=ProviderResponse)
async def approve_provider(
    provider_id: str,
    body: ApprovalRequest,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(ProviderProfile).where(ProviderProfile.id == provider_id)
    )
    provider = result.scalar_one_or_none()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    provider.status = body.status.value

    if body.status == ProviderStatus.approved:
        provider.approved_at = datetime.now(timezone.utc)
        provider.rejected_at = None
    elif body.status == ProviderStatus.rejected:
        provider.rejected_at = datetime.now(timezone.utc)
        provider.approved_at = None
    await db.commit()
    await db.refresh(provider)
    await db.refresh(provider, attribute_names=["categories"])
    return provider

# Explicit ban
@router.patch("/{user_id}/ban")
async def ban_user(
    user_id: str,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="User is already banned")

    user.is_active = False
    await db.commit()
    await db.refresh(user)
    return user


# Explicit unban
@router.patch("/{user_id}/unban")
async def unban_user(
    user_id: str,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.is_active:
        raise HTTPException(status_code=400, detail="User is not banned")

    user.is_active = True
    await db.commit()
    await db.refresh(user)
    return user

# Delete
@router.delete("/{user_id}/")
async def ban_user(
    user_id: str,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_active = False
    await db.delete(user)
    await db.commit()
    return {"message": "User deleted"}
