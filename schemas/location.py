from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID
from datetime import datetime


class SavedLocationCreate(BaseModel):
    label: str = Field(min_length=1, max_length=100)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    address: Optional[str] = None
    is_default: bool = False


class SavedLocationUpdate(BaseModel):
    label: Optional[str] = Field(default=None, min_length=1, max_length=100)
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    address: Optional[str] = None
    is_default: Optional[bool] = None


class SavedLocationResponse(BaseModel):
    id: UUID
    label: str
    latitude: float
    longitude: float
    address: Optional[str] = None
    is_default: bool
    created_at: datetime

    class Config:
        from_attributes = True
