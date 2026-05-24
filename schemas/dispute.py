from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID
from datetime import datetime
from decimal import Decimal


class DisputeCreate(BaseModel):
    booking_id: UUID
    reason: str = Field(min_length=10, max_length=2000)


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