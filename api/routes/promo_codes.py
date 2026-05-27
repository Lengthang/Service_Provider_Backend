from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List
from db.database import get_db
from models.promo import PromoCode, PromoRedemption
from schemas.promo_code import ActivePromoResponse, PromoCodeCreate, PromoCodeResponse
from core.dependencies import get_admin_user, get_current_user
from models.user import User
from datetime import datetime, timezone
from decimal import Decimal

router = APIRouter(prefix="/admin/promo-codes", tags=["Promo Codes"])

# Fallbacks used when a promo has no custom copy set. Mirror the frontend's
# built-in strings so old promos keep looking exactly as they do today.
_DEFAULT_TITLE = "WELCOME OFFER"
_DEFAULT_HEADLINE = "{percent}% off your\nfirst service"
_DEFAULT_CTA = "USE {code}"


def _format_percent(value: Decimal) -> str:
    """20.00 -> '20', 12.50 -> '12.5'."""
    s = format(value, "f")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s


def _build_active_promo(promo: PromoCode) -> ActivePromoResponse:
    """Apply defaults + substitute {percent}/{code} so copy is display-ready."""
    percent = _format_percent(promo.discount_percentage)

    def render(template: str) -> str:
        return template.replace("{percent}", percent).replace("{code}", promo.code)

    return ActivePromoResponse(
        id=promo.id,
        code=promo.code,
        discount_percentage=promo.discount_percentage,
        expires_at=promo.expires_at,
        title=render(promo.title or _DEFAULT_TITLE),
        headline=render(promo.headline or _DEFAULT_HEADLINE),
        subtitle=render(promo.subtitle) if promo.subtitle else None,
        cta_label=render(promo.cta_label or _DEFAULT_CTA),
    )

# --- Admin: create a promo code ---
@router.post("/", response_model=PromoCodeResponse, status_code=201)
async def create_promo_code(
    data: PromoCodeCreate,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(PromoCode).where(PromoCode.code == data.code)
    )
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Promo code already exists")
    
    promo = PromoCode(**data.model_dump())
    db.add(promo)
    await db.commit()
    await db.refresh(promo)
    return promo
# --- Admin: view all promo codes ---
@router.get("/", response_model=List[PromoCodeResponse])
async def get_all_promo_codes(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(PromoCode))
    return result.scalars().all()


# --- Admin: deactivate a promo code ---
@router.patch("/{promo_id}", response_model=PromoCodeResponse)
async def deactivate_promo_code(
    promo_id: str,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
): 
    result = await db.execute(
        select(PromoCode).where(PromoCode.id == promo_id)
    )
    promo = result.scalar_one_or_none()
    if not promo:
        raise HTTPException(status_code=404, detail="Promo code not found")
    
    promo.is_active = False
    await db.commit()
    await db.refresh(promo)
    return promo

public_router = APIRouter(prefix="/promo-codes", tags=["Promo Codes"])


@public_router.get("/active", response_model=List[ActivePromoResponse])
async def get_active_promo_codes(db: AsyncSession = Depends(get_db)):
    """
    Active promos visible to any authenticated user. Filters by:
      - is_active = True
      - not expired
      - not globally exhausted
    Per-user usage is enforced at checkout, not here.
    """
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(PromoCode).where(
            PromoCode.is_active.is_(True),
            (PromoCode.expires_at.is_(None)) | (PromoCode.expires_at > now),
            (PromoCode.max_uses.is_(None)) | (PromoCode.current_uses < PromoCode.max_uses),
        ).order_by(PromoCode.discount_percentage.desc())
    )
    return [_build_active_promo(p) for p in result.scalars().all()]