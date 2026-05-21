from sqlalchemy import Column, ForeignKey, Integer, Numeric, DateTime, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from db.database import Base
from datetime import datetime, timezone
import uuid


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class BookingItem(Base):
    __tablename__ = "booking_items"
    __table_args__ = (
        CheckConstraint("quantity >= 1", name="ck_booking_items_quantity_positive"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    booking_id = Column(
        UUID(as_uuid=True),
        ForeignKey("bookings.id", ondelete="CASCADE"),
        nullable=False,
    )
    service_id = Column(
        UUID(as_uuid=True),
        ForeignKey("services.id", ondelete="RESTRICT"),
        nullable=False,
    )
    quantity = Column(Integer, nullable=False)
    unit_price_at_booking = Column(Numeric(10, 2), nullable=False)
    line_total_at_booking = Column(Numeric(10, 2), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    booking = relationship("Booking", back_populates="items")
    service = relationship("Service")
