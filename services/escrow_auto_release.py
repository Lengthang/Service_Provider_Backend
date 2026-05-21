from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from datetime import datetime, timezone

from models.payment import BookingConfirmation, EscrowAccount
from models.booking import Booking, BookingStatusHistory
from services.wallet_service import release_escrow_to_provider

async def auto_release_expired_escrows(db: AsyncSession):
    """
    Called periodically (e.g. every 15 minutes).
    Finds confirmations where:
      - provider has confirmed
      - customer has NOT confirmed
      - auto_release_at has passed
    Releases escrow and completes the booking automatically.
    """
    now = datetime.now(timezone.utc)

    result = await db.execute(
        select(BookingConfirmation).where(
            BookingConfirmation.provider_confirmed == True,
            BookingConfirmation.customer_confirmed == False,
            BookingConfirmation.auto_release_at <= now
        )
    )

    stale_confirmations = result.scalars().all()

    for confirmation in stale_confirmations:
        result = await db.execute(
            select(Booking).where(Booking.id == confirmation.booking_id)
        )
        booking = result.scalar_one_or_none()
        if not booking or booking.status != "awaiting_confirmation":
            continue

        # auto-confirm on behalf of customer
        confirmation.customer_confirmed = True
        confirmation.customer_confirmed_at = now
        confirmation.auto_release_at = None

        # release escrow
        result = await db.execute(
            select(EscrowAccount).where(
                EscrowAccount.booking_id == booking.id,
                EscrowAccount.status == "holding"
            )
        )
        escrow = result.scalar_one_or_none()
        if escrow:
            await release_escrow_to_provider(db, booking, escrow)

        booking.status = "completed"
        db.add(BookingStatusHistory(
            booking_id=booking.id,
            status="completed",
            changed_by=None  # system action, no user
        ))

    await db.commit()
    return len(stale_confirmations)
