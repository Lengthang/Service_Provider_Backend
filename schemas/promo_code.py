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
    # Optional promo-card copy. Leave null to use the frontend defaults.
    # headline / cta_label may contain {percent} and {code} placeholders.
    title: Optional[str] = Field(default=None, max_length=60)
    headline: Optional[str] = Field(default=None, max_length=120)
    subtitle: Optional[str] = Field(default=None, max_length=160)
    cta_label: Optional[str] = Field(default=None, max_length=40)

class PromoCodeResponse(BaseModel):
    id: UUID
    code: str
    discount_percentage: Decimal
    max_uses: Optional[int]
    max_uses_per_user: int
    current_uses: int
    expires_at: Optional[datetime]
    is_active: bool
    # Raw stored templates (may be null / contain placeholders).
    title: Optional[str] = None
    headline: Optional[str] = None
    subtitle: Optional[str] = None
    cta_label: Optional[str] = None
    class Config:
        from_attributes = True

class ActivePromoResponse(BaseModel):
    id: UUID
    code: str
    discount_percentage: Decimal
    expires_at: Optional[datetime] = None
    # Render-ready card copy: defaults applied and {percent}/{code} substituted.
    # The frontend can display these directly. subtitle is null when unset.
    title: str
    headline: str
    subtitle: Optional[str] = None
    cta_label: str

    class Config:
        from_attributes = True