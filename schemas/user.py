from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from schemas.provider import AvailabilityResponse, ProviderDetailResponse, ProviderResponse
from schemas.service import ServiceResponse


class CustomerUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    google_id: Optional[str] = None
    profile_photo_url: Optional[str] = None
    
# --- Provider Response ---
class UserResponse(BaseModel):
    id: UUID
    name: Optional[str] = None
    email: Optional[str] = None
    phone: str
    role: str
    google_id: Optional[str] = None
    profile_photo_url: Optional[str] = None
    is_active: bool
    updated_at: datetime
    created_at: datetime

    class Config:
        from_attributes = True

class UserDetailResponse(UserResponse):
    provider_profile: Optional[ProviderDetailResponse] = None

    class Config:
        from_attributes = True