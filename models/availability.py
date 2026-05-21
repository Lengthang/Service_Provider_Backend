from sqlalchemy import Column, String, Time, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from db.database import Base
import uuid

class ProviderAvailability(Base):
    __tablename__ = "provider_availability"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider_id = Column(UUID(as_uuid=True), ForeignKey("provider_profiles.id", ondelete="CASCADE"), nullable=False)
    day_of_week = Column(String(10), nullable=False)
    open_time = Column(Time, nullable=False)
    close_time = Column(Time, nullable=False)

    provider = relationship("ProviderProfile", back_populates="availability")