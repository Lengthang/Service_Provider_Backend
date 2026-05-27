import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Boolean, DateTime, Integer, Numeric, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from db.database import Base


def _utcnow():
    return datetime.now(timezone.utc)


class PromoCode(Base):
    __tablename__ = "promo_codes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(String(50), unique=True, nullable=False)
    discount_percentage = Column(Numeric(5, 2), nullable=False)
    max_uses = Column(Integer, nullable=True)
    max_uses_per_user = Column(Integer, default=1)
    current_uses = Column(Integer, default=0)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    title = Column(String(60), nullable=True)       # eyebrow, e.g. "NEW YEAR OFFER"
    headline = Column(String(120), nullable=True)   # big text, supports \n + {percent}
    subtitle = Column(String(160), nullable=True)   # optional fine print under headline
    cta_label = Column(String(40), nullable=True)   # button text, supports {code}

class PromoRedemption(Base):
    __tablename__ = "promo_redemptions"
    __table_args__ = (
        # prevent a single booking from redeeming the same code twice (race-safe)
        UniqueConstraint("promo_code_id", "booking_id", name="uq_promo_per_booking"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    promo_code_id = Column(UUID(as_uuid=True), ForeignKey("promo_codes.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    booking_id = Column(UUID(as_uuid=True), ForeignKey("bookings.id"), nullable=False)
    discount_applied = Column(Numeric(10, 2), nullable=False)
    redeemed_at = Column(DateTime(timezone=True), default=_utcnow)

    promo_code = relationship("PromoCode", backref="redemptions")
    user = relationship("User", backref="promo_redemptions")