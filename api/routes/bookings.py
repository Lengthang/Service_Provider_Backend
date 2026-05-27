from uuid import UUID
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from typing import List
from core.enums import BookingStatus
from db.database import get_db
from models.booking import Booking, BookingStatusHistory
from models.booking_item import BookingItem
from models.user import User
from models.provider import ProviderProfile
from models.payment import EscrowAccount
from models.wallet import WalletTransaction
from schemas.booking import (
    BookingCreate,
    BookingResponse,
    ProviderBookingResponse,
    BookingPayoutOut,
    BookingStatusUpdate,
    BookingPhotoCreate,
    BookingPhotoResponse,
    PricePreviewRequest,
    PricePreviewResponse,
)
from services.booking_service import (
    create_booking,
    update_booking_status,
    compute_price_preview,
    add_booking_photo,
    list_booking_photos,
    delete_booking_photo,
)
from services.wallet_service import split_commission
from core.config import settings
from core.dependencies import get_current_user
from core.distance import haversine_km

router = APIRouter(prefix="/bookings", tags=["Bookings"])

# --- Customer: create a booking ---
@router.post("/", response_model=BookingResponse)
async def make_booking(
    body: BookingCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    booking = await create_booking(current_user, body, db)
    return serialize_booking(booking)


# --- Customer: view their own bookings ---
@router.get("/my", response_model=List[BookingResponse])
async def view(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Booking)
        .where(Booking.customer_id == current_user.id)
        .options(*booking_with_relations())
        .order_by(Booking.created_at.desc())
    )
    bookings = result.scalars().all()
    return [serialize_booking(b) for b in bookings]

# --- Provider: view bookings assigned to them ---
@router.get("/provider", response_model=List[ProviderBookingResponse])
async def provider_bookings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(ProviderProfile).where(ProviderProfile.user_id == current_user.id)
    )
    provider = result.scalar_one_or_none()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider profile not found")

    result = await db.execute(
        select(Booking)
        .where(Booking.provider_id == provider.id)
        .options(*booking_with_relations())
        .order_by(Booking.created_at.desc())
    )
    bookings = result.scalars().all()
    return [serialize_booking(b, include_payout=True) for b in bookings]

# --- Public: real-time price preview for a multi-service cart ---
@router.post("/price-preview", response_model=PricePreviewResponse)
async def price_preview(
    body: PricePreviewRequest,
    db: AsyncSession = Depends(get_db),
):
    return await compute_price_preview(body.items, db)


# --- Get a single booking by ID ---
@router.get("/{booking_id}", response_model=BookingResponse)
async def get_booking(
    booking_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Booking).where(Booking.id == booking_id)
        .options(*booking_with_relations())
    )
    booking = result.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    # Only the customer or provider involved can view it
    provider_result = await db.execute(
        select(ProviderProfile).where(ProviderProfile.user_id == current_user.id)
    )
    provider = provider_result.scalar_one_or_none()
    is_customer = str(booking.customer_id) == str(current_user.id)
    is_provider = provider and str(booking.provider_id) == str(provider.id)

    if not is_customer and not is_provider and current_user.role != 'admin':
        raise HTTPException(status_code=403, detail="Access denied")
    return serialize_booking(booking)


# --- Provider/admin: payout breakdown for a single booking ---
@router.get("/{booking_id}/payout", response_model=BookingPayoutOut)
async def booking_payout(
    booking_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Booking).where(Booking.id == booking_id))
    booking = result.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    # Only the assigned provider (or an admin) may see payout figures.
    provider_result = await db.execute(
        select(ProviderProfile).where(ProviderProfile.user_id == current_user.id)
    )
    provider = provider_result.scalar_one_or_none()
    is_provider = provider and str(booking.provider_id) == str(provider.id)
    if not is_provider and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only the assigned provider can view payout")

    result = await db.execute(
        select(EscrowAccount).where(EscrowAccount.booking_id == booking_id)
    )
    escrow = result.scalar_one_or_none()
    escrow_status = escrow.status if escrow else "none"

    if escrow and escrow.status == "released":
        # Actual settled amounts, read from the recorded transactions
        # (covers normal release and dispute release/partial).
        result = await db.execute(
            select(WalletTransaction).where(
                WalletTransaction.reference_id == str(booking_id),
                WalletTransaction.type.in_(["escrow_release", "commission"]),
            )
        )
        txns = result.scalars().all()
        provider_payout = sum((t.amount for t in txns if t.type == "escrow_release"), Decimal("0.00"))
        platform_commission = sum((t.amount for t in txns if t.type == "commission"), Decimal("0.00"))
        gross_amount = escrow.amount
        is_estimate = False
    elif escrow and escrow.status == "refunded":
        # Customer was refunded; the provider received nothing.
        provider_payout = Decimal("0.00")
        platform_commission = Decimal("0.00")
        gross_amount = escrow.amount
        is_estimate = False
    else:
        # Not yet released — project from the current total at the current rate.
        platform_commission, provider_payout = split_commission(booking.total_amount)
        gross_amount = booking.total_amount
        is_estimate = True

    return {
        "booking_id": booking.id,
        "currency": settings.CURRENCY,
        "gross_amount": gross_amount,
        "provider_payout": provider_payout,
        "platform_commission": platform_commission,
        "commission_rate": settings.PLATFORM_COMMISSION_RATE,
        "escrow_status": escrow_status,
        "is_estimate": is_estimate,
    }

# --- Update booking status ---
@router.patch("/{booking_id}/status", response_model=BookingResponse)
async def update_status(
    booking_id: UUID,
    body: BookingStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):    
    try:
        new_status = BookingStatus(body.status)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid status: {body.status}")

    booking = await update_booking_status(booking_id, new_status, current_user, db)
    return serialize_booking(booking)


# --- Provider: attach a before/after photo to a job ---
# Upload the image first via POST /uploads/image, then post the returned URL here.
@router.post("/{booking_id}/photos", response_model=BookingPhotoResponse, status_code=201)
async def add_photo(
    booking_id: UUID,
    body: BookingPhotoCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await add_booking_photo(booking_id, body, current_user, db)


# --- Customer/provider/admin: list a job's before/after photos ---
@router.get("/{booking_id}/photos", response_model=List[BookingPhotoResponse])
async def get_photos(
    booking_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await list_booking_photos(booking_id, current_user, db)


# --- Provider: remove a photo they attached ---
@router.delete("/{booking_id}/photos/{photo_id}", status_code=204)
async def remove_photo(
    booking_id: UUID,
    photo_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await delete_booking_photo(booking_id, photo_id, current_user, db)


# ── Helper for consistent eager loading ──
def booking_with_relations():
    return [
        selectinload(Booking.status_history),
        selectinload(Booking.customer),
        selectinload(Booking.items).selectinload(BookingItem.service),
        selectinload(Booking.provider).selectinload(ProviderProfile.user),
        selectinload(Booking.photos),
    ]


def serialize_booking(b: Booking, include_payout: bool = False) -> dict:
    provider_lat = b.provider.latitude if b.provider else None
    provider_lng = b.provider.longitude if b.provider else None
    distance_km = haversine_km(b.latitude, b.longitude, provider_lat, provider_lng)

    data = {
        "id": b.id,
        "customer_id": b.customer_id,
        "provider_id": b.provider_id,
        "status": b.status,
        "scheduled_at": b.scheduled_at,
        "address": b.address,
        "latitude": float(b.latitude) if b.latitude is not None else None,
        "longitude": float(b.longitude) if b.longitude is not None else None,
        "notes": b.notes,
        "created_at": b.created_at,
        "subtotal": b.subtotal,
        "discount_amount": b.discount_amount,
        "total_amount": b.total_amount,
        "currency": settings.CURRENCY,
        "distance_km": distance_km,
        "customer": (
            {
                "id": b.customer.id,
                "name": b.customer.name,
                "profile_photo_url": b.customer.profile_photo_url,
            }
            if b.customer else None
        ),
        "provider": (
            {
                "id": b.provider.id,
                "name": b.provider.user.name,
                "profile_photo_url": b.provider.profile_photo_url,
                "avg_rating": float(b.provider.avg_rating or 0),
            }
            if b.provider and b.provider.user else None
        ),
        "items": [
            {
                "service_id": item.service_id,
                "title": item.service.title if item.service else None,
                "image_url": item.service.image_url if item.service else None,
                "quantity": item.quantity,
                "unit_price": item.unit_price_at_booking,
                "line_total": item.line_total_at_booking,
                "duration_minutes": item.service.duration_minutes if item.service else None,
            }
            for item in (b.items or [])
        ],
        "photos": [
            {
                "id": photo.id,
                "url": photo.url,
                "kind": photo.kind,
                "uploaded_at": photo.uploaded_at,
            }
            for photo in (b.photos or [])
        ],
        "status_history": b.status_history,
    }

    if include_payout:
        commission, provider_net = split_commission(b.total_amount)
        data["provider_payout"] = provider_net
        data["platform_commission"] = commission

    return data
