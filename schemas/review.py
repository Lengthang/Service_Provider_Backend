from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID
from datetime import datetime
from decimal import Decimal


class ReviewCreate(BaseModel):
    booking_id: UUID
    rating: int = Field(ge=1, le=5)
    comment: Optional[str] = Field(default=None, max_length=2000)


class ReviewCustomer(BaseModel):
    id: UUID
    name: Optional[str] = None
    profile_photo_url: Optional[str] = None

    class Config:
        from_attributes = True


class ReviewOut(BaseModel):
    id: UUID
    booking_id: UUID
    customer_id: UUID
    provider_id: UUID
    rating: int
    comment: Optional[str] = None
    created_at: datetime
    customer: Optional[ReviewCustomer] = None

    class Config:
        from_attributes = True


class ProviderRatingSummary(BaseModel):
    provider_id: UUID
    avg_rating: Decimal
    total_reviews: int