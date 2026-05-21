from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from fastapi import HTTPException
from decimal import Decimal
from datetime import datetime, timedelta, timezone
from uuid import UUID
from core.config import settings
from models.provider import ProviderProfile
from models.wallet import Wallet, WalletTransaction
from models.payment import (
    Payment, EscrowAccount, BookingConfirmation,
    SavedPaymentMethod, WithdrawalRequest
)
from models.promo import PromoCode, PromoRedemption
from models.booking import Booking, BookingStatusHistory
from models.user import User
from services.wallet_service import release_escrow_to_provider, hold_in_escrow

async def charge_and_hold_escrow(
    db: AsyncSession,
    user: User,
    booking: Booking,
    method: str,
    promo_code: str | None,
    subtotal: Decimal,
) -> Payment:
    """
    Apply any promo to the given subtotal, charge the customer, and hold the
    funds in escrow against the given booking. Caller is responsible for the
    surrounding transaction (commit/rollback) and for setting booking.status.
    Returns the Payment row; the caller should also persist
    booking.subtotal / booking.discount_amount / booking.total_amount.
    """
    amount = Decimal(subtotal)
    discount = Decimal("0.00")
    promo_id = None

    # apply promo
    if promo_code:
        result = await db.execute(
            select(PromoCode)
            .where(
                PromoCode.code == promo_code,
                PromoCode.is_active == True
            )
        )
        promo = result.scalar_one_or_none()
        if not promo:
            raise HTTPException(status_code=400, detail="Invalid promo code")
        if promo.max_uses is not None and promo.current_uses >= promo.max_uses:
            raise HTTPException(status_code=400, detail="Promo code fully used")
        if promo.expires_at and promo.expires_at < datetime.now(timezone.utc):
            raise HTTPException(status_code=400, detail="Promo code expired")
        result = await db.execute(
            select(func.count(PromoRedemption.id)).where(
                PromoRedemption.promo_code_id == promo.id,
                PromoRedemption.user_id == user.id
            )
        )
        user_uses = result.scalar() or 0
        if user_uses >= promo.max_uses_per_user:
            raise HTTPException(
                status_code=400,
                detail="You have already used this promo code"
            )
        discount = amount * promo.discount_percentage / 100
        promo_id = promo.id
        promo.current_uses += 1
        db.add(PromoRedemption(
            promo_code_id=promo.id,
            user_id=user.id,
            booking_id=booking.id,
            discount_applied=discount
        ))

    final_amount = amount - discount

    payment = Payment(
        booking_id=booking.id,
        amount=final_amount,
        discount_amount=discount,
        promo_code_id=promo_id,
        method=method,
        status="paid",
        paid_at=datetime.now(timezone.utc)
    )
    db.add(payment)

    await hold_in_escrow(db, booking, final_amount, user.id)
    return payment


async def confirm_booking_completion(
    db: AsyncSession, 
    user: User, 
    booking_id: UUID, 
    role: str
) -> BookingConfirmation:
    
    # load booking
    result = await db.execute(
        select(Booking).where(Booking.id == booking_id)
    )
    booking = result.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    if booking.status != "awaiting_confirmation":
        raise HTTPException(
            status_code=400,
            detail=f"Booking must be 'awaiting_confirmation', currently '{booking.status}'"
        )
    
    result = await db.execute(
        select(BookingConfirmation).where(BookingConfirmation.booking_id == booking_id)
    )
    confirmation = result.scalar_one_or_none()
    if not confirmation:
        raise HTTPException(status_code=404, detail="No confirmation record (cash payment?)")
    
    # determine role
    is_customer = str(booking.customer_id) == str(user.id)
    provider_result = await db.execute(
        select(ProviderProfile).where(ProviderProfile.user_id == user.id)
    )
    provider = provider_result.scalar_one_or_none()
    is_provider = provider and str(provider.id) == str(booking.provider_id)

    if not is_customer and not is_provider:
        raise HTTPException(status_code=403, detail="Not involved in this booking")
    
    now = datetime.now(timezone.utc)

    if is_provider:
        if confirmation.provider_confirmed:
            raise HTTPException(status_code=400, detail="Provider already confirmed")
        confirmation.provider_confirmed = True
        confirmation.provider_confirmed_at = now
        # start the auto-release countdown
        confirmation.auto_release_at = now + timedelta(hours=settings.ESCROW_AUTO_RELEASE_HOURS)
        
    elif is_customer:
        if confirmation.customer_confirmed:
            raise HTTPException(status_code=400, detail="Customer already confirmed")
        confirmation.customer_confirmed = True
        confirmation.customer_confirmed_at = now
        # customer confirmed, no need for auto-release
        confirmation.auto_release_at = None
    
    # if both confirmed → release escrow and complete booking
    if confirmation.provider_confirmed and confirmation.customer_confirmed:
        await _release_and_complete(db, booking, booking_id, user.id)
    await db.commit()
    await db.refresh(confirmation)
    return confirmation

async def _release_and_complete(
    db: AsyncSession,
    booking: Booking,
    booking_id: UUID,
    changed_by
):
    """Shared logic for both manual and auto release."""
    result = await db.execute(
        select(EscrowAccount).where(
            EscrowAccount.booking_id == booking_id,
            EscrowAccount.status == "holding"
        )
    )
    escrow = result.scalar_one_or_none()
    if escrow:
        await release_escrow_to_provider(db, booking, escrow)
    booking.status = "completed"
    db.add(BookingStatusHistory(
        booking_id=booking.id, status="completed", changed_by=changed_by
    ))