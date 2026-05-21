import uuid
from sqlalchemy import Column, String, Text, Numeric, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from db.database import Base


class Dispute(Base):
    __tablename__ = "disputes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    booking_id = Column(UUID(as_uuid=True), ForeignKey("bookings.id"), unique=True, nullable=False)
    raised_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    reason = Column(Text, nullable=False)
    status = Column(String(20), default="open")  # open, resolved
    resolution = Column(String(20), nullable=True)  # release, refund, partial
    resolution_note = Column(Text, nullable=True)
    provider_payout = Column(Numeric(12, 2), nullable=True)  # for partial resolution
    customer_refund = Column(Numeric(12, 2), nullable=True)  # for partial resolution
    resolved_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    booking = relationship("Booking", backref="dispute")
    raiser = relationship("User", foreign_keys=[raised_by], backref="disputes_raised")
    resolver = relationship("User", foreign_keys=[resolved_by])