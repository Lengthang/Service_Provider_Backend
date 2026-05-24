from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from db.database import get_db
from models.user import User
from schemas.auth import SendOTPRequest, VerifyOTPRequest, TokenResponse
from services.otp_service import send_otp, verify_otp
from core.security import create_access_token
from core.config import settings
from sqlalchemy.orm import selectinload

router = APIRouter(prefix="/auth", tags=["Auth"])

@router.post("/send-otp")
async def send_otp_route(body: SendOTPRequest):
    success = send_otp(body.phone)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to send OTP")
    return {"message": "OTP sent successfully"}

@router.post("/verify-otp", response_model=TokenResponse)
async def verify_otp_route(body: VerifyOTPRequest, db: AsyncSession = Depends(get_db)):
    # Check OTP with Twilio
    is_valid = verify_otp(body.phone, body.code)
    if not is_valid:
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")

    # eager-load provider_profile if it exists
    result = await db.execute(
        select(User)
        .options(selectinload(User.provider_profile))
        .where(User.phone == body.phone)
    )
    user = result.scalar_one_or_none()

    is_new_user = False

    if not user:
        # New user — create account
        # if not body.name:
        #     raise HTTPException(status_code=400, detail="Name is required for new users")
        user = User(phone=body.phone, name=body.name)
        db.add(user)
        await db.commit()
        await db.refresh(user)
        is_new_user = True

    token = create_access_token(str(user.id))
    return TokenResponse(
        access_token=token,
        is_new_user=is_new_user,
        provider_profile=user.provider_profile if user.provider_profile else None
    )


@router.post("/dev-token", response_model=TokenResponse)
async def dev_token(phone: str, db: AsyncSession = Depends(get_db)):
    if settings.ENV != "development":
        raise HTTPException(status_code=403, detail="Not allowed in production")

    result = await db.execute(
        select(User)
        .options(selectinload(User.provider_profile))
        .where(User.phone == phone)
    )
    user = result.scalar_one_or_none()
    is_new_user = False

    if not user:
        user = User(phone=phone)
        db.add(user)
        await db.commit()
        # Refresh AND populate the relationship in one shot
        await db.refresh(user, attribute_names=["provider_profile"])
        is_new_user = True

    return TokenResponse(
        access_token=create_access_token(str(user.id)),  # also fix: real JWT, not "dev-token-{id}"
        is_new_user=is_new_user,
        provider_profile=user.provider_profile,
    )