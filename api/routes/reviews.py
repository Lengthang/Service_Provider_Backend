from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from typing import List

from db.database import get_db
from core.dependencies import get_current_user
from models.user import User
from models.review import Review
from schemas.review import ReviewCreate, ReviewOut, ProviderRatingSummary
from services.review_service import (
    create_review, get_provider_reviews, get_provider_rating_summary
)

router = APIRouter(prefix="/reviews", tags=["Reviews"])


@router.post("/", response_model=ReviewOut, status_code=201)
async def write_review(
    data: ReviewCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    return await create_review(db, user, data)


@router.get("/my", response_model=List[ReviewOut])
async def my_reviews(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Review)
        .options(selectinload(Review.customer))
        .where(Review.customer_id == user.id)
        .order_by(Review.created_at.desc())
    )
    return result.scalars().all()


@router.get("/providers/{provider_id}", response_model=List[ReviewOut])
async def provider_reviews(
    provider_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    return await get_provider_reviews(db, provider_id)


@router.get("/providers/{provider_id}/summary", response_model=ProviderRatingSummary)
async def provider_rating_summary(
    provider_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    return await get_provider_rating_summary(db, provider_id)


@router.get("/booking/{booking_id}", response_model=ReviewOut)
async def review_for_booking(
    booking_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Review)
        .options(selectinload(Review.customer))
        .where(Review.booking_id == booking_id)
    )
    review = result.scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=404, detail="No review for this booking")
    return review