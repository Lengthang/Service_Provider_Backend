from sqlalchemy import Column, String, Boolean, DateTime, Text, Numeric, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from db.database import Base
from datetime import datetime, timezone
import uuid


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SavedLocation(Base):
    """A service location a customer has saved for reuse when booking.

    Customers aren't always at the place that needs service, so a booking's
    location is decoupled from the device's current GPS fix: at booking time the
    customer can pick one of these instead. The booking copies the coordinates
    (see services.booking_service.create_booking), so editing or deleting a saved
    location never affects bookings already made from it.
    """
    __tablename__ = "saved_locations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    label = Column(String(100), nullable=False)            # e.g. "Home", "Office"
    latitude = Column(Numeric(9, 6), nullable=False)
    longitude = Column(Numeric(9, 6), nullable=False)
    address = Column(Text, nullable=True)                  # human-readable, optional
    is_default = Column(Boolean, default=False, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    user = relationship("User", backref="saved_locations")
