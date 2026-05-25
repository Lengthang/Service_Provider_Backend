from sqlalchemy import Column, String, ForeignKey, Text, Numeric, Integer, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from db.database import Base
from datetime import datetime, timezone
import uuid

class Service(Base):
    __tablename__ = "services"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider_id = Column(UUID(as_uuid=True), ForeignKey("provider_profiles.id", ondelete="CASCADE"), nullable=False)
    category_id = Column(UUID(as_uuid=True), ForeignKey("categories.id", ondelete="RESTRICT"), nullable=True)
    title = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)
    image_url = Column(Text, nullable=True)
    price = Column(Numeric(10, 2), nullable=False)
    duration_minutes = Column(Integer, nullable=True)
    min_quantity = Column(Integer, nullable=False, default=1)
    is_active = Column(Boolean, nullable=False, default=True)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc),)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    provider = relationship("ProviderProfile", back_populates="services")
    category = relationship("Category")
