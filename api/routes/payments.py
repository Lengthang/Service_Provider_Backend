from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List

from db.database import get_db
from core.dependencies import get_current_user
from models.promo import PromoCode, PromoRedemption
from models.user import User
from models.wallet import Wallet, WalletTransaction
from models.payment import SavedPaymentMethod, Payment
from schemas.payment import (
    WalletOut, WalletTopUpRequest, WalletTransactionOut,
    SavedPaymentMethodCreate, SavedPaymentMethodOut,
    ConfirmationOut,
    WithdrawalCreate, WithdrawalOut
)
from services.payment_service import confirm_booking_completion
from services.wallet_service import get_or_create_wallet, request_withdrawal, top_up_wallet

router = APIRouter(prefix="/payments", tags=["Payments"])


# ── Wallet ──
@router.get("/wallet", response_model=WalletOut)
async def get_wallet(
    user: User = Depends(get_current_user), 
    db: AsyncSession = Depends(get_db)
):
    wallet = await get_or_create_wallet(db, user.id)
    return wallet


@router.post("/wallet/top-up", response_model=WalletOut)
async def wallet_top_up(
    data: WalletTopUpRequest, 
    user: User = Depends(get_current_user), 
    db: AsyncSession = Depends(get_db)
):
    return await top_up_wallet(db, user.id, data.amount, data.payment_method_id)


@router.get("/wallet/transactions", response_model=List[WalletTransactionOut])
async def get_wallet_transactions(
    user: User = Depends(get_current_user), 
    db: AsyncSession = Depends(get_db)
):
    wallet = await get_or_create_wallet(db, user.id)
    result = await db.execute(
        select(WalletTransaction).where(WalletTransaction.wallet_id == wallet.id)
        .order_by(WalletTransaction.created_at.desc())
    )
    return result.scalars().all()


# ── Saved Payment Methods ──
@router.get("/methods", response_model=List[SavedPaymentMethodOut])
async def list_payment_methods(
    user: User = Depends(get_current_user), 
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(SavedPaymentMethod).where(SavedPaymentMethod.user_id == user.id)
    )
    return result.scalars().all()


@router.post("/methods", response_model=SavedPaymentMethodOut, status_code=201)
async def add_payment_method(
    data: SavedPaymentMethodCreate, 
    user: User = Depends(get_current_user), 
    db: AsyncSession = Depends(get_db)
):
    method = SavedPaymentMethod(user_id=user.id, **data.model_dump())
    db.add(method)
    await db.commit()
    await db.refresh(method)
    return method


@router.delete("/methods/{method_id}", status_code=204)
async def delete_payment_method(
    method_id: str, 
    user: User = Depends(get_current_user), 
    db: AsyncSession = Depends(get_db)
):
    from fastapi import HTTPException
    result = await db.execute(
        select(SavedPaymentMethod).where(SavedPaymentMethod.id == method_id, SavedPaymentMethod.user_id == user.id)
    )
    method = result.scalar_one_or_none()
    if not method:
        raise HTTPException(status_code=404, detail="Not found")
    await db.delete(method)
    await db.commit()


# ── Confirm Completion ──
@router.post("/confirm/{booking_id}", response_model=ConfirmationOut)
async def confirm_completion(
    booking_id: str, 
    user: User = Depends(get_current_user), 
    db: AsyncSession = Depends(get_db)
):
    return await confirm_booking_completion(db, user, booking_id, user.role)


# ── Withdrawals ──
@router.post("/withdraw", response_model=WithdrawalOut, status_code=201)
async def withdraw(
    data: WithdrawalCreate, 
    user: User = Depends(get_current_user), 
    db: AsyncSession = Depends(get_db)
):
    return await request_withdrawal(db, user, data.amount, data.payment_method_id)

@router.get("/promo-codes/{code}/validate")
async def validate_promo_code(
    code: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(PromoCode).where(PromoCode.code == code, PromoCode.is_active == True)
    )
    promo = result.scalar_one_or_none()
    if not promo:
        raise HTTPException(status_code=404, detail="Promo code not found")

    if promo.expires_at and promo.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Promo code expired")

    if promo.max_uses is not None and promo.current_uses >= promo.max_uses:
        raise HTTPException(status_code=400, detail="Promo code fully used")

    result = await db.execute(
        select(func.count(PromoRedemption.id)).where(
            PromoRedemption.promo_code_id == promo.id,
            PromoRedemption.user_id == user.id
        )
    )
    user_uses = result.scalar() or 0
    if user_uses >= promo.max_uses_per_user:
        raise HTTPException(status_code=400, detail="You have already used this promo code")

    return {
        "code": promo.code,
        "discount_percentage": promo.discount_percentage,
        "valid": True
    }