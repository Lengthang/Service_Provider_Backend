from uuid import UUID
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from fastapi import HTTPException

from models.dispute import Dispute
from models.booking import Booking, BookingStatusHistory
from models.payment import EscrowAccount, BookingConfirmation
from models.user import User
from schemas.dispute import DisputeCreate, DisputeResolve
from services.wallet_service import (
    release_escrow_to_provider, refund_escrow_to_customer,
    get_or_create_wallet, credit_provider_payout,
)
from models.wallet import WalletTransaction

async def create_dispute(
    db: AsyncSession,
    user: User,
    data: DisputeCreate
):
    
    # verify booking exists and is in the right state
    result = await db.execute(
        select(Booking).where(
            Booking.id == data.booking_id
        )
    )
    booking = result.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    # only the customer can raise a dispute
    if str(booking.customer_id) != str(user.id):
        raise HTTPException(status_code=403, detail="Only the customer can raise a dispute")
    
    if booking.status != "awaiting_confirmation" :
        raise HTTPException(
            status_code=400,
            detail=f"Disputes can only be raised during 'awaiting_confirmation', currently '{booking.status}'"
        )
    
    # check no existing dispute
    result = await db.execute(
        select(Dispute).where(Dispute.booking_id == data.booking_id)
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="A dispute already exists for this booking")

    # clear auto-release timer
    result = await db.execute(
        select(BookingConfirmation).where(BookingConfirmation.booking_id == data.booking_id)
    )
    confirmation = result.scalar_one_or_none()
    if confirmation:
        confirmation.auto_release_at = None

    # move booking to disputed
    booking.status = "disputed"
    db.add(BookingStatusHistory(
        booking_id=booking.id, status="disputed", changed_by=user.id
    ))

    dispute = Dispute(
        booking_id=data.booking_id,
        raised_by=user.id,
        reason=data.reason
    )
    db.add(dispute)
    await db.commit()
    await db.refresh(dispute)
    return dispute

async def resolve_dispute(
    db: AsyncSession, 
    admin: User, 
    dispute_id: UUID, 
    data: DisputeResolve
) -> Dispute:
    
    result = await db.execute(
        select(Dispute).where(Dispute.id == dispute_id)
    )
    dispute = result.scalar_one_or_none()
    if not dispute:
        raise HTTPException(status_code=404, detail="Dispute not found")
    if dispute.status != "open":
        raise HTTPException(status_code=400, detail="Dispute already resolved")
    
    # load booking and escrow
    result = await db.execute(
        select(Booking).where(Booking.id == dispute.booking_id)
    )
    booking = result.scalar_one_or_none()

    result = await db.execute(
        select(EscrowAccount).where(
            EscrowAccount.booking_id == dispute.booking_id,
            EscrowAccount.status == "holding"
        )
    )
    escrow = result.scalar_one_or_none()
    if not escrow:
        raise HTTPException(status_code=400, detail="No active escrow found for this booking")
    
    now = datetime.now(timezone.utc)

    if data.resolution == "release":
        # full escrow to provider, net of platform commission
        provider_net, commission = await release_escrow_to_provider(db, booking, escrow)
        booking.status = "completed"
        dispute.provider_payout = provider_net
        dispute.customer_refund = Decimal("0.00")
        dispute.platform_commission = commission

    elif data.resolution == "refund":
        # full refund to customer
        await refund_escrow_to_customer(db, booking, escrow)
        booking.status = "cancelled"
        dispute.provider_payout = Decimal("0.00")
        dispute.customer_refund = escrow.amount
        dispute.platform_commission = Decimal("0.00")

    elif data.resolution == "partial":
        # split the escrow between both parties
        if data.provider_payout is None or data.customer_refund is None:
            raise HTTPException(
                status_code=400,
                detail="Partial resolution requires both provider_payout and customer_refund amounts"
            )
        if data.provider_payout < 0 or data.customer_refund < 0:
            raise HTTPException(
                status_code=400,
                detail="provider_payout and customer_refund must be non-negative"
            )

        # provider_payout / customer_refund are the gross split of the escrow;
        # the platform commission is then taken out of the provider's share.
        total = data.provider_payout + data.customer_refund
        if total != escrow.amount:
            raise HTTPException(
                status_code=400,
                detail=f"provider_payout + customer_refund must equal escrow amount ({escrow.amount})"
            )

        # credit provider their share, net of platform commission
        provider_net, commission = await credit_provider_payout(
            db, booking, data.provider_payout, "Partial escrow release (dispute resolved)"
        )

        # refund customer
        customer_wallet = await get_or_create_wallet(db, booking.customer_id)
        customer_wallet.balance += data.customer_refund
        db.add(WalletTransaction(
            wallet_id=customer_wallet.id, type="refund", amount=data.customer_refund,
            reference_id=str(booking.id),
            description=f"Partial refund (dispute resolved)"
        ))

        escrow.status = "released"
        escrow.released_at = now
        booking.status = "completed"
        dispute.provider_payout = provider_net
        dispute.customer_refund = data.customer_refund
        dispute.platform_commission = commission

    db.add(BookingStatusHistory(
        booking_id=booking.id, status=booking.status, changed_by=admin.id
    ))

    dispute.status = "resolved"
    dispute.resolution = data.resolution
    dispute.resolution_note = data.resolution_note
    dispute.resolved_by = admin.id
    dispute.resolved_at = now

    await db.commit()
    await db.refresh(dispute)
    return dispute