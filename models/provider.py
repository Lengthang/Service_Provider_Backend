from sqlalchemy import Column, String, Boolean, DateTime, Integer, Text, Numeric, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from core.enums import ProviderStatus
from db.database import Base
from datetime import datetime, timezone
import uuid


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ProviderProfile(Base):
    __tablename__ = "provider_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    bio = Column(Text, nullable=True)
    profile_photo_url = Column(Text, nullable=True)
    years_experience = Column(Integer, default=0, nullable=False)
    certification = Column(Text, nullable=True)
    certification_url = Column(Text, nullable=True)
    location = Column(String(255), nullable=True)
    latitude = Column(Numeric(9, 6), nullable=True)
    longitude = Column(Numeric(9, 6), nullable=True)
    service_radius_km = Column(Integer, default=10, nullable=False)
    avg_rating = Column(Numeric(2, 1), default=0.0, nullable=False)
    is_available = Column(Boolean, default=True, nullable=False)
    status = Column(String(20), default=ProviderStatus.pending.value, nullable=False)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    rejected_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    user = relationship("User", back_populates="provider_profile")
    availability = relationship("ProviderAvailability", back_populates="provider")
    services = relationship("Service", back_populates="provider")
    categories = relationship(                                # ← NEW: see #5 below
        "Category",
        secondary="provider_categories",
        backref="providers"
    )