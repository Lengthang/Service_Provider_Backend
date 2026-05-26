from pydantic import BaseModel, Field
from typing import List, Optional
from uuid import UUID
from datetime import datetime
from decimal import Decimal


class DisputeCreate(BaseModel):
    booking_id: UUID
    reason: str = Field(min_length=10, max_length=2000)
    reason_image_urls: List[str] = Field(default_factory=list, max_length=10)


class DisputeRespond(BaseModel):
    response: str = Field(min_length=10, max_length=2000)
    response_image_urls: List[str] = Field(default_factory=list, max_length=10)


class DisputeResolve(BaseModel):
    resolution: str = Field(pattern="^(release|refund|partial)$")
    resolution_note: Optional[str] = None
    provider_payout: Optional[Decimal] = None  # required if partial
    customer_refund: Optional[Decimal] = None  # required if partial


class DisputeOut(BaseModel):
    id: UUID
    booking_id: UUID
    raised_by: UUID
    reason: str
    reason_image_urls: List[str] = []
    provider_response: Optional[str] = None
    provider_response_image_urls: List[str] = []
    provider_responded_at: Optional[datetime] = None
    status: str
    resolution: Optional[str] = None
    resolution_note: Optional[str] = None
    provider_payout: Optional[Decimal] = None
    customer_refund: Optional[Decimal] = None
    platform_commission: Optional[Decimal] = None
    resolved_by: Optional[UUID] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class CustomerDisputeOut(BaseModel):
    """Customer-facing view: hides the provider's response and the
    commission/provider-payout figures (the customer only sees their own refund)."""
    id: UUID
    booking_id: UUID
    raised_by: UUID
    reason: str
    reason_image_urls: List[str] = []
    status: str
    resolution: Optional[str] = None
    resolution_note: Optional[str] = None
    customer_refund: Optional[Decimal] = None
    resolved_by: Optional[UUID] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True