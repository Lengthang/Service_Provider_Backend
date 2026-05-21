from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from db.database import get_db
from models.user import User
from models.provider import ProviderProfile
from schemas.user import UserResponse, CustomerUpdate, UserDetailResponse
from schemas.provider import ProviderResponse
from services.provider_service import register_provider
from core.dependencies import get_current_user, get_admin_user
from uuid import UUID
from sqlalchemy.orm import selectinload
router = APIRouter(prefix="/customer", tags=["Customer"])

# --- Get own user profile ---
@router.get("/me", response_model=UserDetailResponse)
async def get_my_profile(
    me: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(User)
        .options(
            selectinload(User.provider_profile)
            .selectinload(ProviderProfile.availability),
            selectinload(User.provider_profile)
            .selectinload(ProviderProfile.services),
            selectinload(User.provider_profile)
            .selectinload(ProviderProfile.categories),
        )
        .where(User.id == me.id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User profile not found")
    return user

# --- Edit own profile ---
@router.patch("/me", response_model=UserResponse)
async def update_my_profile(
    body: CustomerUpdate,
    me: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(User).where(User.id == me.id)
    )

    user = result.scalar_one_or_none()
    if not user:
       raise HTTPException(status_code=404, detail="User profile not found")
    if body.name is not None:
        user.name = body.name
    if body.email is not None:
        user.email = body.email
    if body.phone is not None:
        user.phone = body.phone
    if body.google_id is not None:
        user.google_id = body.google_id
    if body.profile_photo_url is not None:
        user.profile_photo_url = body.profile_photo_url

    await db.commit()
    await db.refresh(user)
    return user
