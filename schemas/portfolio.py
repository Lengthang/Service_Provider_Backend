from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID
from datetime import datetime


class PortfolioItemCreate(BaseModel):
    before_photo_url: str = Field(min_length=1, max_length=2000)
    after_photo_url: str = Field(min_length=1, max_length=2000)
    caption: Optional[str] = Field(default=None, max_length=500)


class PortfolioItemUpdate(BaseModel):
    before_photo_url: Optional[str] = Field(default=None, min_length=1, max_length=2000)
    after_photo_url: Optional[str] = Field(default=None, min_length=1, max_length=2000)
    caption: Optional[str] = Field(default=None, max_length=500)


class PortfolioItemOut(BaseModel):
    id: UUID
    provider_id: UUID
    before_photo_url: str
    after_photo_url: str
    caption: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True