from sqlalchemy import Column, String, Numeric, ForeignKey, DateTime, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from db.database import Base
from datetime import datetime, timezone
import uuid


def _utcnow():
    return datetime.now(timezone.utc)


class SavedPaymentMethod(Base):
    __tablename__ = "saved_payment_methods"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    type = Column(String(10), nullable=False)  # card, bank
    display_name = Column(String(100), nullable=False)
    last_four = Column(String(4))
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    user = relationship("User", backref="saved_payment_methods")

class EscrowAccount(Base):
    __tablename__ = "escrow_accounts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    booking_id = Column(UUID(as_uuid=True), ForeignKey("bookings.id"), unique=True, nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    status = Column(String(20), default="holding", nullable=False)  # holding, released, refunded
    released_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    booking = relationship("Booking", backref="escrow")


class BookingConfirmation(Base):
    __tablename__ = "booking_confirmations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    booking_id = Column(UUID(as_uuid=True), ForeignKey("bookings.id"), unique=True, nullable=False)
    provider_confirmed = Column(Boolean, default=False, nullable=False)
    provider_confirmed_at = Column(DateTime(timezone=True))
    customer_confirmed = Column(Boolean, default=False, nullable=False)
    customer_confirmed_at = Column(DateTime(timezone=True))
    auto_release_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    booking = relationship("Booking", backref="confirmation")


class Payment(Base):
    __tablename__ = "payments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    booking_id = Column(UUID(as_uuid=True), ForeignKey("bookings.id"), nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    discount_amount = Column(Numeric(10, 2), default=0.00, nullable=False)
    promo_code_id = Column(UUID(as_uuid=True), ForeignKey("promo_codes.id"), nullable=True)
    method = Column(String(30), nullable=False)  # cash, card, bank, wallet
    status = Column(String(20), default="unpaid", nullable=False)  # unpaid, paid, refunded
    paid_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    booking = relationship("Booking", backref="payment")


class WithdrawalRequest(Base):
    __tablename__ = "withdrawal_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    payment_method_id = Column(UUID(as_uuid=True), ForeignKey("saved_payment_methods.id"), nullable=False)
    status = Column(String(20), default="pending")  # pending, processed, failed
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    user = relationship("User", backref="withdrawal_requests")
    payment_method = relationship("SavedPaymentMethod")