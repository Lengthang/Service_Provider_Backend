from uuid import UUID

from pydantic import BaseModel
from typing import Optional

class SendOTPRequest(BaseModel):
    phone: str

class VerifyOTPRequest(BaseModel):
    phone: str
    code: str
    name: Optional[str] = None   # only needed on first-time signup

class ProviderProfileMini(BaseModel):
    """Minimal provider info on auth — full details from /providers/me."""
    id: UUID
    status: str          # pending | approved | rejected
    is_available: bool
    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    is_new_user: bool
    provider_profile: Optional[ProviderProfileMini] = None  