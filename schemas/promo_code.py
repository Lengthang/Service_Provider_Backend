from decimal import Decimal

from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID
from datetime import datetime

class PromoCodeCreate(BaseModel):
    code: str = Field(min_length=3, max_length=50)
    discount_percentage: Decimal = Field(gt=0, le=100)
    max_uses: Optional[int] = None        # null = unlimited globally
    max_uses_per_user: int = 1
    expires_at: Optional[datetime] = None

class PromoCodeResponse(BaseModel):
    id: UUID
    code: str
    discount_percentage: Decimal
    max_uses: Optional[int]
    max_uses_per_user: int
    current_uses: int
    expires_at: Optional[datetime]
    is_active: bool
    class Config:
        from_attributes = True

class ActivePromoResponse(BaseModel):
    id: UUID
    code: str
    discount_percentage: Decimal
    expires_at: Optional[datetime] = None

    class Config:
        from_attributes = True