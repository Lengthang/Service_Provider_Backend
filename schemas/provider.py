from pydantic import BaseModel, Field
from typing import Optional, List
from uuid import UUID
from core.enums import ProviderStatus
from schemas.service import ServiceResponse
from datetime import datetime, time
from schemas.category import CategoryResponse  

class AvailabilityResponse(BaseModel):
    id: UUID
    day_of_week: str
    open_time: time
    close_time: time
    
    class Config:
        from_attributes = True

# --- Provider Registration ---
_DAY_PATTERN = "^(monday|tuesday|wednesday|thursday|friday|saturday|sunday)$"
_TIME_PATTERN = r"^([01]\d|2[0-3]):[0-5]\d$"  # HH:MM, 24h


class AvailabilityInput(BaseModel):
    day_of_week: str = Field(pattern=_DAY_PATTERN)
    open_time: str = Field(pattern=_TIME_PATTERN)    # e.g. "08:00"
    close_time: str = Field(pattern=_TIME_PATTERN)   # e.g. "17:00"



class ProviderRegisterRequest(BaseModel):
    bio: Optional[str] = None
    profile_photo_url: Optional[str] = Field(default=None, min_length=1, max_length=2000)
    years_experience: int = Field(default=0, ge=0)
    certification: Optional[str] = None
    certification_url: Optional[str] = None
    national_id_url: Optional[str] = None
    location: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    service_radius_km: int = Field(default=10, ge=1, le=100)
    category_ids: List[UUID] = []
    availability: List[AvailabilityInput]


class ProviderUpdate(BaseModel):
    bio: Optional[str] = None
    profile_photo_url: Optional[str] = Field(default=None, min_length=1, max_length=2000)
    years_experience: Optional[int] = Field(default=None, ge=0)
    certification: Optional[str] = None
    certification_url: Optional[str] = None
    national_id_url: Optional[str] = None
    location: Optional[str] = None
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    service_radius_km: Optional[int] = Field(default=None, ge=1, le=100)
    is_available: Optional[bool] = None
    category_ids: Optional[List[UUID]] = None
    availability: Optional[List[AvailabilityInput]] = None


class ProviderResponse(BaseModel):
    id: UUID
    user_id: UUID
    bio: Optional[str] = None
    profile_photo_url: Optional[str] = None
    years_experience: int = 0
    certification: Optional[str] = None
    certification_url: Optional[str] = None
    national_id_url: Optional[str] = None
    location: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    service_radius_km: int = 10
    avg_rating: float
    is_available: bool
    status: ProviderStatus
    created_at: datetime
    distance_km: Optional[float] = None
    categories: List[CategoryResponse] = []
    availability: List[AvailabilityResponse] = []    
    class Config:
        from_attributes = True


class ApprovalRequest(BaseModel):
    status: ProviderStatus


class ProviderListItem(BaseModel):
    id: UUID
    user_id: UUID
    name: Optional[str] = None
    bio: Optional[str] = None
    profile_photo_url: Optional[str] = None
    location: Optional[str] = None
    avg_rating: float
    is_available: bool
    service_radius_km: int = 10
    distance_km: Optional[float] = None
    categories: List[CategoryResponse] = []

    class Config:
        from_attributes = True


class ProviderDetailResponse(ProviderResponse):
    name: Optional[str] = None
    availability: List[AvailabilityResponse] = []
    services: List[ServiceResponse] = []
    categories: List[CategoryResponse] = []
    class Config:
        from_attributes = True