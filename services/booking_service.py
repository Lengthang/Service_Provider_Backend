from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from fastapi import HTTPException
from core.config import settings
from core.enums import BookingStatus, ProviderStatus, UserRole
from models.booking import Booking, BookingStatusHistory, BookingPhoto
from models.booking_item import BookingItem
from models.location import SavedLocation
from models.payment import EscrowAccount, Payment
from models.provider import ProviderProfile
from models.service import Service
from models.availability import ProviderAvailability
from models.user import User
from schemas.booking import BookingCreate, PricePreviewItem, BookingPhotoCreate
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from sqlalchemy.orm import selectinload
from services.wallet_service import (
    refund_escrow_to_customer
)
from services.payment_service import charge_and_hold_escrow
"""
Status flow:
  Customer books and pays upfront → pending (escrow holds funds)
         → in_progress (provider accepts)
         → awaiting_confirmation (provider marks job done)
         → completed (dual confirm, escrow released)
  pending → rejected (provider rejects, escrow refunded)
  Any active status → cancelled by customer (triggers refund if escrow exists)
"""

VALID_TRANSITIONS = {
    "pending":                ["in_progress", "cancelled", "rejected"],
    "in_progress":            ["awaiting_confirmation", "cancelled"],
    "awaiting_confirmation":  ["completed", "disputed", "cancelled"],
    "completed":              [],
    "cancelled":              [],
    "rejected":               [],
    "disputed":               ["completed", "cancelled"],
}

# Customers may cancel an accepted (in_progress) booking only up to this long
# before the scheduled time, so providers aren't stranded by last-minute drops.
CANCELLATION_BUFFER_HOURS = 24
CANCELLATION_BUFFER = timedelta(hours=CANCELLATION_BUFFER_HOURS)

async def compute_price_preview(
    items: list[PricePreviewItem],
    db: AsyncSession,
) -> dict:
    seen: set = set()
    for item in items:
        if item.service_id in seen:
            raise HTTPException(
                status_code=400,
                detail=f"Duplicate service_id in cart: {item.service_id}"
            )
        seen.add(item.service_id)

    service_ids = [item.service_id for item in items]
    result = await db.execute(select(Service).where(Service.id.in_(service_ids)))
    services_by_id = {s.id: s for s in result.scalars().all()}

    missing = [sid for sid in service_ids if sid not in services_by_id]
    if missing:
        raise HTTPException(
            status_code=404,
            detail=f"Service(s) not found: {[str(m) for m in missing]}"
        )

    inactive = [str(s.id) for s in services_by_id.values() if not s.is_active]
    if inactive:
        raise HTTPException(
            status_code=400,
            detail=f"Service(s) not available: {inactive}"
        )

    provider_ids = {s.provider_id for s in services_by_id.values()}
    if len(provider_ids) > 1:
        raise HTTPException(
            status_code=400,
            detail="All services must belong to the same provider"
        )
    provider_id = next(iter(provider_ids))

    line_items = []
    subtotal = Decimal("0.00")
    total_duration = 0
    has_any_duration = False
    cents = Decimal("0.01")

    for item in items:
        s = services_by_id[item.service_id]
        if item.quantity < s.min_quantity:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Service '{s.title}' requires a minimum quantity of "
                    f"{s.min_quantity}"
                )
            )
        line_total = (Decimal(s.price) * item.quantity).quantize(cents)
        line_items.append({
            "service_id": s.id,
            "title": s.title,
            "unit_price": s.price,
            "quantity": item.quantity,
            "line_total": line_total,
            "duration_minutes": s.duration_minutes,
        })
        subtotal += line_total
        if s.duration_minutes:
            total_duration += s.duration_minutes * item.quantity
            has_any_duration = True

    return {
        "provider_id": provider_id,
        "currency": settings.CURRENCY,
        "items": line_items,
        "subtotal": subtotal.quantize(cents),
        "total": subtotal.quantize(cents),
        "estimated_duration_minutes": total_duration if has_any_duration else None,
    }


async def create_booking(
    customer: User,
    data: BookingCreate,
    db: AsyncSession
) -> Booking:

    # Validate cart and compute pricing using the same engine as price-preview.
    # Provider is derived from the items — all services in a single booking
    # must belong to the same provider (enforced inside compute_price_preview).
    preview_items = [
        PricePreviewItem(service_id=i.service_id, quantity=i.quantity)
        for i in data.items
    ]
    preview = await compute_price_preview(preview_items, db)
    provider_id = preview["provider_id"]
    subtotal: Decimal = preview["subtotal"]

    # Verify provider is approved and available
    result = await db.execute(
        select(ProviderProfile).where(ProviderProfile.id == provider_id)
    )
    provider = result.scalar_one_or_none()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    if provider.status != ProviderStatus.approved.value:
        raise HTTPException(status_code=400, detail="Provider is not approved")
    if not provider.is_available:
        raise HTTPException(status_code=400, detail="Provider is not available")

    # Check provider availability for the scheduled day
    day_name = data.scheduled_at.strftime("%A").lower()   # e.g. "monday"
    scheduled_time = data.scheduled_at.time()

    result = await db.execute(
        select(ProviderAvailability).where(
            ProviderAvailability.provider_id == provider_id,
            ProviderAvailability.day_of_week == day_name
        )
    )
    slots = result.scalars().all()
    if not slots:
        raise HTTPException(
            status_code=400,
            detail=f"Provider is not available on {day_name.capitalize()}"
        )
    if not any(slot.open_time <= scheduled_time <= slot.close_time for slot in slots):
        windows = ", ".join(f"{s.open_time}-{s.close_time}" for s in slots)
        raise HTTPException(
            status_code=400,
            detail=f"Provider is only available during: {windows}"
        )

    # Resolve the service location. A saved location takes precedence over any
    # inline address/coordinates; otherwise we use the current-GPS fields sent by
    # the client. Either way the coordinates are snapshotted onto the booking, so
    # later edits/deletes of the saved location don't affect this booking.
    if data.saved_location_id is not None:
        result = await db.execute(
            select(SavedLocation).where(
                SavedLocation.id == data.saved_location_id,
                SavedLocation.user_id == customer.id,
            )
        )
        location = result.scalar_one_or_none()
        if not location:
            raise HTTPException(status_code=404, detail="Saved location not found")
        # booking.address is NOT NULL; fall back to the label if no human-readable
        # address was saved.
        address = location.address or location.label
        latitude = location.latitude
        longitude = location.longitude
    else:
        address = data.address
        latitude = data.latitude
        longitude = data.longitude

    # Create the booking (amounts may be patched after escrow if a promo applies)
    booking = Booking(
        customer_id=customer.id,
        provider_id=provider_id,
        scheduled_at=data.scheduled_at,
        address=address,
        latitude=latitude,
        longitude=longitude,
        notes=data.notes,
        subtotal=subtotal,
        discount_amount=Decimal("0.00"),
        total_amount=subtotal,
        status="pending",
    )
    db.add(booking)
    await db.flush()

    # Persist line items with the price the customer agreed to at booking time
    for line in preview["items"]:
        db.add(BookingItem(
            booking_id=booking.id,
            service_id=line["service_id"],
            quantity=line["quantity"],
            unit_price_at_booking=line["unit_price"],
            line_total_at_booking=line["line_total"],
        ))

    # Record initial status in history
    db.add(BookingStatusHistory(
        booking_id=booking.id,
        status="pending",
        changed_by=customer.id
    ))

    # Charge customer and hold funds in escrow upfront.
    # If this fails, the whole transaction rolls back and no booking is persisted.
    payment = await charge_and_hold_escrow(
        db=db,
        user=customer,
        booking=booking,
        method=data.method,
        promo_code=data.promo_code,
        subtotal=subtotal,
    )
    booking.discount_amount = payment.discount_amount or Decimal("0.00")
    booking.total_amount = payment.amount

    await db.commit()
    result = await db.execute(
        select(Booking)
        .options(
            selectinload(Booking.status_history),
            selectinload(Booking.customer),
            selectinload(Booking.items).selectinload(BookingItem.service),
            selectinload(Booking.provider).selectinload(ProviderProfile.user),
            selectinload(Booking.photos),
            selectinload(Booking.review),
        )
        .where(Booking.id == booking.id)
    )
    return result.scalar_one()

async def update_booking_status(
    booking_id: UUID,
    new_status: BookingStatus,
    current_user: User,
    db: AsyncSession
) -> Booking:

    result = await db.execute(
        select(Booking)
        .options(selectinload(Booking.status_history)) 
        .where(Booking.id == booking_id)
    )
    booking = result.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    # ── Reject transitions this function doesn't own ──
    if new_status == BookingStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail="Completion requires dual confirmation via POST /payments/confirm/{booking_id}"
        )

    # ── Permission checks ──
    is_customer = str(booking.customer_id) == str(current_user.id)

    provider_result = await db.execute(
        select(ProviderProfile).where(ProviderProfile.user_id == current_user.id)
    )
    provider = provider_result.scalar_one_or_none()
    is_assigned_provider = provider and str(provider.id) == str(booking.provider_id)

    if new_status == BookingStatus.CANCELLED:
        if booking.status == "pending":
            # customer can back out before the provider has accepted
            if not is_customer:
                raise HTTPException(status_code=403, detail="Only the customer can cancel a pending booking")
        elif booking.status == "in_progress":
            if is_customer:
                # Provider has accepted but work happens on the scheduled day;
                # allow the customer to back out until the buffer window closes.
                if datetime.now(timezone.utc) >= booking.scheduled_at - CANCELLATION_BUFFER:
                    raise HTTPException(
                        status_code=403,
                        detail=f"Bookings can only be cancelled up to {CANCELLATION_BUFFER_HOURS} hours "
                               "before the scheduled time. Wait for completion and raise a dispute if needed."
                    )
            elif not is_assigned_provider:
                raise HTTPException(
                    status_code=403,
                    detail="Not authorized to cancel this booking"
                )
        elif booking.status == "awaiting_confirmation":
            raise HTTPException(
                status_code=400,
                detail="Cannot cancel a completed job. Use POST /disputes/ to raise a dispute."
            )

        elif booking.status == "disputed":
            raise HTTPException(
                status_code=400,
                detail="Disputed bookings can only be resolved by admin via PATCH /disputes/{id}/resolve"
            )

        else:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot cancel a booking in '{booking.status}' status"
            )
    elif new_status == BookingStatus.REJECTED:
        # Only the assigned provider can reject, and only while pending
        if not is_assigned_provider:
            raise HTTPException(status_code=403, detail="Only the assigned provider can reject a booking")
    elif new_status == BookingStatus.IN_PROGRESS:
        # Provider acceptance
        if not is_assigned_provider:
            raise HTTPException(status_code=403, detail="Only the assigned provider can accept this booking")
    elif new_status == BookingStatus.DISPUTED:
        if not is_customer:
            raise HTTPException(status_code=403, detail="Only the customer can dispute a booking")
    elif new_status == BookingStatus.AWAITING_CONFIRMATION:
        if not is_assigned_provider:
            raise HTTPException(
                status_code=403,
                detail="Only the assigned provider can update this booking"
            )

    # ── Validate transition ──
    allowed = VALID_TRANSITIONS.get(booking.status, [])
    if new_status.value not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot move booking from '{booking.status}' to '{new_status.value}'"
        )
    # ── Handle escrow refund (cancel by customer or rejection by provider) ──
    if new_status in (BookingStatus.CANCELLED, BookingStatus.REJECTED):
        result = await db.execute(
            select(EscrowAccount).where(
                EscrowAccount.booking_id == booking_id,
                EscrowAccount.status == "holding"
            )
        )
        escrow = result.scalar_one_or_none()
        if escrow:
            await refund_escrow_to_customer(db, booking, escrow)

    booking.status = new_status.value

    history = BookingStatusHistory(
        booking_id=booking.id,
        status=new_status.value,
        changed_by=current_user.id
    )
    db.add(history)

    await db.commit()

    result = await db.execute(
        select(Booking)
        .options(
            selectinload(Booking.status_history),
            selectinload(Booking.customer),
            selectinload(Booking.items).selectinload(BookingItem.service),
            selectinload(Booking.provider).selectinload(ProviderProfile.user),
            selectinload(Booking.photos),
            selectinload(Booking.review),
        )
        .where(Booking.id == booking.id)
    )
    return result.scalar_one()


# Photos document the job while it's being done; once it's settled
# (completed/cancelled/rejected) or disputed, the gallery is frozen.
PHOTO_EDITABLE_STATUSES = {"in_progress", "awaiting_confirmation"}


async def _booking_for_assigned_provider(
    booking_id: UUID,
    current_user: User,
    db: AsyncSession,
) -> Booking:
    """Load a booking and assert current_user is its assigned provider."""
    result = await db.execute(select(Booking).where(Booking.id == booking_id))
    booking = result.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    result = await db.execute(
        select(ProviderProfile).where(ProviderProfile.user_id == current_user.id)
    )
    provider = result.scalar_one_or_none()
    if not provider or str(provider.id) != str(booking.provider_id):
        raise HTTPException(
            status_code=403,
            detail="Only the assigned provider can manage this booking's photos",
        )
    return booking


async def add_booking_photo(
    booking_id: UUID,
    data: BookingPhotoCreate,
    current_user: User,
    db: AsyncSession,
) -> BookingPhoto:
    booking = await _booking_for_assigned_provider(booking_id, current_user, db)

    if booking.status not in PHOTO_EDITABLE_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=(
                "Photos can only be added while the job is in progress or "
                f"awaiting confirmation (currently '{booking.status}')"
            ),
        )

    photo = BookingPhoto(
        booking_id=booking.id,
        url=data.url,
        kind=data.kind,
        uploaded_by=current_user.id,
    )
    db.add(photo)
    await db.commit()
    await db.refresh(photo)
    return photo


async def list_booking_photos(
    booking_id: UUID,
    current_user: User,
    db: AsyncSession,
) -> list[BookingPhoto]:
    """Return the booking's photos for anyone allowed to see the booking
    (its customer, its assigned provider, or an admin)."""
    result = await db.execute(select(Booking).where(Booking.id == booking_id))
    booking = result.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    is_customer = str(booking.customer_id) == str(current_user.id)
    result = await db.execute(
        select(ProviderProfile).where(ProviderProfile.user_id == current_user.id)
    )
    provider = result.scalar_one_or_none()
    is_provider = provider and str(provider.id) == str(booking.provider_id)
    if not is_customer and not is_provider and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Access denied")

    result = await db.execute(
        select(BookingPhoto)
        .where(BookingPhoto.booking_id == booking_id)
        .order_by(BookingPhoto.uploaded_at)
    )
    return list(result.scalars().all())


async def delete_booking_photo(
    booking_id: UUID,
    photo_id: UUID,
    current_user: User,
    db: AsyncSession,
) -> None:
    booking = await _booking_for_assigned_provider(booking_id, current_user, db)

    if booking.status not in PHOTO_EDITABLE_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=(
                "Photos can only be removed while the job is in progress or "
                f"awaiting confirmation (currently '{booking.status}')"
            ),
        )

    result = await db.execute(
        select(BookingPhoto).where(
            BookingPhoto.id == photo_id,
            BookingPhoto.booking_id == booking_id,
        )
    )
    photo = result.scalar_one_or_none()
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")

    await db.delete(photo)
    await db.commit()