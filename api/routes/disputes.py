from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List

from  db.database import get_db
from core.dependencies import get_current_user, get_admin_user
from models.user import User
from models.dispute import Dispute
from models.booking import Booking
from models.provider import ProviderProfile
from schemas.dispute import (
    DisputeCreate, DisputeOut, CustomerDisputeOut, DisputeRespond, DisputeResolve
)
from services.dispute_service import create_dispute, respond_to_dispute, resolve_dispute

router = APIRouter(prefix="/disputes", tags=["Disputes"])

@router.post("/", response_model=CustomerDisputeOut, status_code=201)
async def raise_dispute(
    data: DisputeCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    return await create_dispute(db, user, data)


@router.get("/my", response_model=List[CustomerDisputeOut])
async def my_disputes(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Dispute).where(Dispute.raised_by == user.id)
        .order_by(Dispute.created_at.desc())
    )
    return result.scalars().all()


# ── Provider: disputes filed against their bookings ──
@router.get("/provider", response_model=List[DisputeOut])
async def provider_disputes(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(ProviderProfile).where(ProviderProfile.user_id == user.id)
    )
    provider = result.scalar_one_or_none()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider profile not found")

    result = await db.execute(
        select(Dispute)
        .join(Booking, Dispute.booking_id == Booking.id)
        .where(Booking.provider_id == provider.id)
        .order_by(Dispute.created_at.desc())
    )
    return result.scalars().all()


@router.get("/{dispute_id}", response_model=None)
async def get_dispute(
    dispute_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Dispute).where(Dispute.id == dispute_id))
    dispute = result.scalar_one_or_none()
    if not dispute:
        raise HTTPException(status_code=404, detail="Dispute not found")

    # admins see the full record
    if user.role == "admin":
        return DisputeOut.model_validate(dispute)

    # the customer who raised it gets the restricted view (no provider response,
    # no commission/provider-payout figures)
    if str(dispute.raised_by) == str(user.id):
        return CustomerDisputeOut.model_validate(dispute)

    # the assigned provider gets the full record
    booking_result = await db.execute(
        select(Booking).where(Booking.id == dispute.booking_id)
    )
    booking = booking_result.scalar_one_or_none()
    provider_result = await db.execute(
        select(ProviderProfile).where(ProviderProfile.user_id == user.id)
    )
    provider = provider_result.scalar_one_or_none()
    is_provider = provider and booking and str(booking.provider_id) == str(provider.id)
    if not is_provider:
        raise HTTPException(status_code=403, detail="Access denied")
    return DisputeOut.model_validate(dispute)


# ── Provider: respond to a dispute ──
@router.patch("/{dispute_id}/respond", response_model=DisputeOut)
async def respond(
    dispute_id: UUID,
    data: DisputeRespond,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    return await respond_to_dispute(db, user, dispute_id, data)


# ── Admin only ──
@router.get("/", response_model=List[DisputeOut])
async def list_all_disputes(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Dispute).order_by(Dispute.created_at.desc())
    )
    return result.scalars().all()


@router.patch("/{dispute_id}/resolve", response_model=DisputeOut)
async def resolve(
    dispute_id: UUID,
    data: DisputeResolve,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    return await resolve_dispute(db, admin, dispute_id, data)