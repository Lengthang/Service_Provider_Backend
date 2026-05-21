from sqlalchemy import Column, String, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID
from db.database import Base
from datetime import datetime, timezone
from core.enums import UserRole
import uuid
from sqlalchemy.orm import relationship


def utcnow() -> datetime:
    """Timezone-aware UTC now. Replaces the deprecated datetime.utcnow()."""
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=True)
    email = Column(String(255), unique=True, nullable=True)
    phone = Column(String(20), unique=True, nullable=False)
    role = Column(String(20), default=UserRole.customer.value, nullable=False)
    google_id = Column(String(255), unique=True, nullable=True)
    profile_photo_url = Column(String, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    provider_profile = relationship("ProviderProfile", back_populates="user", uselist=False)