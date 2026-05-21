from decimal import Decimal
from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID
from datetime import datetime

# ── Wallet ──
class WalletOut(BaseModel):
    id: UUID
    balance: Decimal
    class Config:
        from_attributes = True

class WalletTopUpRequest(BaseModel):
    amount: Decimal = Field(gt=0)
    payment_method_id: UUID


class WalletTransactionOut(BaseModel):
    id: UUID
    type: str
    amount: Decimal
    reference_id: Optional[str] = None
    description: Optional[str] = None
    created_at: datetime
    class Config:
        from_attributes = True

# ── Saved Payment Methods ──
class SavedPaymentMethodCreate(BaseModel):
    type: str = Field(pattern="^(card|bank)$")
    display_name: str
    last_four: Optional[str] = None
    is_default: bool = False


class SavedPaymentMethodOut(BaseModel):
    id: UUID
    type: str
    display_name: str
    last_four: Optional[str] = None
    is_default: bool
    class Config:
        from_attributes = True

# ── Payment ──
class PaymentCreate(BaseModel):
    booking_id: UUID
    method: str = Field(pattern="^(cash|card|bank|wallet)$")
    promo_code: Optional[str] = None


class PaymentOut(BaseModel):
    id: UUID
    booking_id: UUID
    amount: Decimal
    discount_amount: Decimal
    method: Optional[str] = None
    status: str
    paid_at: Optional[datetime] = None
    created_at: datetime
    class Config:
        from_attributes = True


# ── Booking Confirmation ──
class ConfirmationOut(BaseModel):
    booking_id: UUID
    provider_confirmed: bool
    customer_confirmed: bool
    provider_confirmed_at: Optional[datetime] = None
    customer_confirmed_at: Optional[datetime] = None
    class Config:
        from_attributes = True


# ── Withdrawal ──
class WithdrawalCreate(BaseModel):
    amount: Decimal = Field(gt=0)
    payment_method_id: UUID


class WithdrawalOut(BaseModel):
    id: UUID
    amount: Decimal
    status: str
    created_at: datetime
    class Config:
        from_attributes = True
