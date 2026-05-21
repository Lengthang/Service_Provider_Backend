from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID
from datetime import datetime

class CategoryCreate(BaseModel):
    name: str
    icon_url: Optional[str] = None

class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    icon_url: Optional[str] = None
    is_active: Optional[bool] = None

class CategoryResponse(BaseModel):
    id: UUID
    name: str
    icon_url: Optional[str]
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True