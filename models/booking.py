from sqlalchemy import TIMESTAMP, Column, String, Boolean, DateTime, Integer, Text, Numeric, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from core.enums import BookingStatus
from db.database import Base
from datetime import datetime, timezone
import uuid


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Booking(Base):
    __tablename__ = "bookings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    provider_id = Column(UUID(as_uuid=True), ForeignKey("provider_profiles.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(50), default=BookingStatus.PENDING.value, nullable=False)
    scheduled_at = Column(TIMESTAMP(timezone=True), nullable=False)
    address = Column(Text, nullable=False)
    latitude = Column(Numeric(9, 6), nullable=True)
    longitude = Column(Numeric(9, 6), nullable=True)
    notes = Column(Text, nullable=True)
    subtotal = Column(Numeric(10, 2), nullable=False)
    discount_amount = Column(Numeric(10, 2), nullable=False, default=0)
    total_amount = Column(Numeric(10, 2), nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), default=utcnow)

    customer = relationship("User", backref="bookings")
    provider = relationship("ProviderProfile", backref="bookings")
    items = relationship(
        "BookingItem", back_populates="booking", cascade="all, delete-orphan"
    )
    status_history = relationship("BookingStatusHistory", backref="booking")




class BookingStatusHistory(Base):
    __tablename__ = "booking_status_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    booking_id = Column(UUID(as_uuid=True), ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(50), nullable=False)
    changed_at = Column(DateTime(timezone=True), default=utcnow)
    changed_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

