from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID
from datetime import datetime

class ServiceCreate(BaseModel):
    category_id: UUID
    title: str
    description: Optional[str] = None
    image_url: Optional[str] = Field(default=None, max_length=2000)
    price: float = Field(gt=0)
    duration_minutes: Optional[int] = Field(default=None, gt=0)
    min_quantity: int = Field(default=1, ge=1)

class ServiceUpdate(BaseModel):
    category_id: Optional[UUID] = None
    title: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = Field(default=None, max_length=2000)
    price: Optional[float] = Field(default=None, gt=0)
    duration_minutes: Optional[int] = Field(default=None, gt=0)
    min_quantity: Optional[int] = Field(default=None, ge=1)
    is_active: Optional[bool] = None

class ServiceResponse(BaseModel):
    id: UUID
    provider_id: UUID
    category_id: Optional[UUID] = None
    title: str
    description: Optional[str] = None
    image_url: Optional[str] = None
    price: float
    duration_minutes: Optional[int] = None
    min_quantity: int = 1
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True