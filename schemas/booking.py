from decimal import Decimal

from pydantic import BaseModel, Field, model_validator
from typing import Optional, List
from uuid import UUID
from datetime import datetime

# ── Nested summaries for embedding ──
class CustomerSummary(BaseModel):
    id: UUID
    name: Optional[str] = None
    profile_photo_url: Optional[str] = None
    class Config:
        from_attributes = True


class ProviderSummary(BaseModel):
    id: UUID
    user_id: UUID
    location: Optional[str] = None
    avg_rating: float
    class Config:
        from_attributes = True


class ProviderUserSummary(BaseModel):
    """Provider details from the perspective of a customer's booking — shows the person."""
    id: UUID                  # provider profile id
    name: Optional[str] = None  # provider's user.name
    profile_photo_url: Optional[str] = None
    avg_rating: float
    class Config:
        from_attributes = True


class BookingItemInput(BaseModel):
    service_id: UUID
    quantity: int = Field(ge=1)


class BookingItemResponse(BaseModel):
    service_id: UUID
    title: str
    image_url: Optional[str] = None
    quantity: int
    unit_price: Decimal
    line_total: Decimal
    duration_minutes: Optional[int] = None


class BookingCreate(BaseModel):
    items: List[BookingItemInput] = Field(min_length=1)
    scheduled_at: datetime
    # Service location comes from one of two sources:
    #   • a saved location (set saved_location_id; the server fills in coordinates), or
    #   • the device's current GPS fix (send address + latitude/longitude inline).
    # Exactly one source is required.
    saved_location_id: Optional[UUID] = None
    address: Optional[str] = None
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    notes: Optional[str] = None
    method: str = Field(pattern="^(card|bank|wallet)$")
    promo_code: Optional[str] = None

    @model_validator(mode="after")
    def _require_location_source(self):
        if self.saved_location_id is None and not (self.address and self.address.strip()):
            raise ValueError(
                "Provide either a saved_location_id or an address (with coordinates)"
            )
        return self

class BookingStatusUpdate(BaseModel):
    status: str  # in_progress, awaiting_confirmation, completed, cancelled, rejected


# ── Before/after job photos (provider-supplied) ──
class BookingPhotoCreate(BaseModel):
    url: str = Field(min_length=1, max_length=2000)  # from POST /uploads/image
    kind: str = Field(pattern="^(before|after)$")


class BookingPhotoResponse(BaseModel):
    id: UUID
    url: str
    kind: str
    uploaded_at: datetime

    class Config:
        from_attributes = True


class StatusHistoryResponse(BaseModel):
    status: str
    changed_by: Optional[UUID] = None
    changed_at: datetime

    class Config:
        from_attributes = True

# ── Price preview (cart) ──
class PricePreviewItem(BaseModel):
    service_id: UUID
    quantity: int = Field(ge=1)


class PricePreviewRequest(BaseModel):
    items: List[PricePreviewItem] = Field(min_length=1)


class PricePreviewLineItem(BaseModel):
    service_id: UUID
    title: str
    unit_price: Decimal
    quantity: int
    line_total: Decimal
    duration_minutes: Optional[int] = None


class PricePreviewResponse(BaseModel):
    provider_id: UUID
    currency: str
    items: List[PricePreviewLineItem]
    subtotal: Decimal
    total: Decimal
    estimated_duration_minutes: Optional[int] = None


class BookingResponse(BaseModel):
    id: UUID
    customer_id: UUID
    provider_id: UUID
    status: str
    scheduled_at: datetime
    address: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    notes: Optional[str]
    created_at: datetime

    subtotal: Decimal
    discount_amount: Decimal
    total_amount: Decimal
    currency: str

    distance_km: Optional[float] = None

    # Embedded for UI rendering
    customer: Optional[CustomerSummary] = None
    provider: Optional[ProviderUserSummary] = None
    items: List[BookingItemResponse] = []
    photos: List[BookingPhotoResponse] = []

    status_history: List[StatusHistoryResponse] = []

    class Config:
        from_attributes = True


class ProviderBookingResponse(BookingResponse):
    """Booking as seen by its assigned provider — adds the provider's payout breakdown.

    These are ESTIMATES based on the current platform commission rate. The actual
    settled amounts are locked in when escrow is released (see the escrow_release
    wallet transaction, or the dispute record if the booking was disputed).
    """
    provider_payout: Optional[Decimal] = None      # estimated net to the provider
    platform_commission: Optional[Decimal] = None  # estimated platform cut


class BookingPayoutOut(BaseModel):
    """Payout breakdown for one booking, for the assigned provider (or admin).

    While the booking is unsettled, the figures are an estimate at the current
    commission rate (is_estimate=True). Once escrow is released/refunded they are
    the actual amounts that moved (is_estimate=False).
    """
    booking_id: UUID
    currency: str
    gross_amount: Decimal           # escrow / total the split is based on
    provider_payout: Decimal
    platform_commission: Decimal
    commission_rate: Decimal
    escrow_status: str              # holding | released | refunded | none
    is_estimate: bool