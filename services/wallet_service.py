from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from fastapi import HTTPException
from models.booking import Booking
from models.payment import BookingConfirmation, EscrowAccount, SavedPaymentMethod, WithdrawalRequest
from models.provider import ProviderProfile
from models.wallet import Wallet, WalletTransaction
from models.user import User
from decimal import Decimal, ROUND_HALF_UP
from core.config import settings

CENTS = Decimal("0.01")


def split_commission(gross: Decimal) -> tuple[Decimal, Decimal]:
    """Split a gross payout into (platform_commission, provider_net).

    The commission is rounded to cents and the provider receives the exact
    remainder, so the two parts always add back up to ``gross``.
    """
    commission = (gross * settings.PLATFORM_COMMISSION_RATE).quantize(CENTS, rounding=ROUND_HALF_UP)
    return commission, gross - commission


async def get_platform_wallet(db: AsyncSession) -> Wallet:
    """Wallet that collects platform commission, identified by PLATFORM_USER_ID."""
    if not settings.PLATFORM_USER_ID:
        raise HTTPException(status_code=500, detail="PLATFORM_USER_ID is not configured")
    result = await db.execute(
        select(User).where(User.id == settings.PLATFORM_USER_ID)
    )
    platform_user = result.scalar_one_or_none()
    if not platform_user:
        raise HTTPException(status_code=500, detail="Configured platform user does not exist")
    return await get_or_create_wallet(db, platform_user.id)


async def credit_provider_payout(
    db: AsyncSession,
    booking: Booking,
    gross: Decimal,
    description: str,
) -> tuple[Decimal, Decimal]:
    """Pay ``gross`` to the booking's provider, net of platform commission.

    Credits the provider's wallet with their net share and routes the
    commission to the platform wallet. Returns (provider_net, commission).
    """
    result = await db.execute(
        select(ProviderProfile).where(ProviderProfile.id == booking.provider_id)
    )
    provider = result.scalar_one_or_none()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found for this booking")

    commission, provider_net = split_commission(gross)

    provider_wallet = await get_or_create_wallet(db, provider.user_id)
    provider_wallet.balance += provider_net
    db.add(WalletTransaction(
        wallet_id=provider_wallet.id,
        type="escrow_release",
        amount=provider_net,
        reference_id=str(booking.id),
        description=description,
    ))

    if commission > 0:
        platform_wallet = await get_platform_wallet(db)
        platform_wallet.balance += commission
        db.add(WalletTransaction(
            wallet_id=platform_wallet.id,
            type="commission",
            amount=commission,
            reference_id=str(booking.id),
            description=f"Platform commission ({settings.PLATFORM_COMMISSION_RATE * 100}%)",
        ))

    return provider_net, commission

async def get_or_create_wallet(
    db: AsyncSession,
    user_id
) -> Wallet:
    result = await db.execute(
        select(Wallet).where(Wallet.user_id == user_id)
    )
    wallet = result.scalar_one_or_none()
    if not wallet:
        wallet = Wallet(user_id=user_id)
        db.add(wallet)
        await db.commit()
        await db.refresh(wallet)

    return wallet

async def top_up_wallet(
    db: AsyncSession,
    user_id: UUID,
    amount: Decimal,
    payment_method_id: UUID,
) -> Wallet:
    result = await db.execute(
        select(SavedPaymentMethod).where(
            SavedPaymentMethod.id == payment_method_id,
            SavedPaymentMethod.user_id == user_id
        )
    )

    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Payment method not found")
    
    wallet = await get_or_create_wallet(db, user_id)
    wallet.balance += amount

    transaction = WalletTransaction(
        wallet_id=wallet.id,
        type="top_up",
        amount=amount,
        description="Top up via payment method"
    )

    db.add(transaction)
    await db.commit()
    await db.refresh(wallet)
    return wallet

async def hold_in_escrow(
    db: AsyncSession,
    booking: Booking, 
    amount: Decimal, 
    customer_id
) -> EscrowAccount:
    """
    Deducts from customer balance and holds in escrow.
    Called when booking is confirmed and customer pays upfront.
    """
    wallet = await get_or_create_wallet(db, customer_id)

    if wallet.balance < amount:
        raise HTTPException(status_code=400, detail="Insufficient wallet balance")

    wallet.balance -= amount

    transaction = WalletTransaction(
        wallet_id=wallet.id,
        type="escrow_hold",
        amount=-amount,
        reference_id=str(booking.id),
        description="Escrow hold for booking"
    )
    db.add(transaction)

    escrow = EscrowAccount(
        booking_id=booking.id,
        amount=amount
    )
    db.add(escrow)

    confirmation = BookingConfirmation(
        booking_id=booking.id
    )
    db.add(confirmation)

    return escrow

async def release_escrow_to_provider(
    db: AsyncSession,
    booking: Booking,
    escrow: EscrowAccount
):
    """
    Release escrow funds to provider wallet, net of platform commission.
    Called when customer confirms completion or auto-release triggers.
    Returns (provider_net, commission).
    """
    provider_net, commission = await credit_provider_payout(
        db, booking, escrow.amount, "Escrow released for completed booking"
    )

    escrow.status = "released"
    escrow.released_at = datetime.now(timezone.utc)
    return provider_net, commission
    
async def refund_escrow_to_customer(
    db: AsyncSession,
    booking: Booking,
    escrow: EscrowAccount
):
    """
    Returns escrow back to customer wallet.
    """
    customer_wallet = await get_or_create_wallet(db, booking.customer_id)
    customer_wallet.balance += escrow.amount

    transaction = WalletTransaction(
        wallet_id=customer_wallet.id, 
        type="refund", 
        amount=escrow.amount,
        reference_id=str(booking.id), 
        description="Refund from cancelled booking"
    )
    db.add(transaction)

    escrow.status = "refunded"

async def request_withdrawal(
    db: AsyncSession,
    user: User,
    amount: Decimal,
    payment_method_id: UUID
) -> WithdrawalRequest:
    
    wallet = await get_or_create_wallet(db, user.id)
    if wallet.balance < amount:
        raise HTTPException(status_code=400, detail="Insufficient wallet balance")
    
    result = await db.execute(
        select(SavedPaymentMethod).where(
            SavedPaymentMethod.id == payment_method_id,
            SavedPaymentMethod.user_id == user.id
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Payment method not found")
    
    wallet.balance -= amount
    transcation = WalletTransaction(
        wallet_id=wallet.id,
        type="withdrawal",
        amount=-amount,
        description="Withdrawal request"
    )
    db.add(transcation)

    withdrawal = WithdrawalRequest(
        user_id=user.id, 
        amount=amount, 
        payment_method_id=payment_method_id
    )
    db.add(withdrawal)
    await db.commit()
    await db.refresh(withdrawal)
    return withdrawal  
