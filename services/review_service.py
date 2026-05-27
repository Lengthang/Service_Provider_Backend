from uuid import UUID
from datetime import datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from sqlalchemy.orm import selectinload
from fastapi import HTTPException

from models.review import Review
from models.booking import Booking
from models.payment import Payment
from models.provider import ProviderProfile
from models.user import User
from schemas.review import ReviewCreate
from core.enums import BookingStatus

async def create_review(
    db: AsyncSession,
    user: User,
    data: ReviewCreate
) -> Review:
    
    # verify booking status
    result = await db.execute(
        select(Booking).where(Booking.id == data.booking_id)
    )
    booking = result.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    # only the customer on the booking can review
    if str(booking.customer_id) != str(user.id):
        raise HTTPException(status_code=403, detail="Only the customer can review this booking")
    
    # must be completed
    if booking.status != BookingStatus.COMPLETED.value:
        raise HTTPException(
            status_code=400,
            detail=f"Can only review completed booking (currently '{booking.status}')"
        )
    
    # must be paid
    result = await db.execute(
        select(Payment).where(
            Payment.booking_id == data.booking_id,
            Payment.status == "paid"
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Booking must be paid before reviewing")
    
    # one review per booking
    result = await db.execute(
        select(Review).where(Review.booking_id == data.booking_id)
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="A review already exists for this booking")
    
    review = Review(
        booking_id=data.booking_id,
        customer_id=user.id,
        provider_id=booking.provider_id,
        rating=data.rating,
        comment=data.comment
    )
    db.add(review)

    # update provider avg_ratting
    await _recalculate_provider_rating(db, booking.provider_id)

    await db.commit()
    await db.refresh(review)
    # `user` is the customer and is already loaded; attach it so the nested
    # `customer` serializes without triggering an async lazy-load.
    review.customer = user
    return review

async def _recalculate_provider_rating(
    db: AsyncSession, 
    provider_id: UUID
):
    """Recompute the provider's average rating from all their reviews."""
    result = await db.execute(
        select(func.avg(Review.rating)).where(Review.provider_id == provider_id)
    )
    avg = result.scalar()

    result = await db.execute(
        select(ProviderProfile).where(ProviderProfile.id == provider_id)
    )
    provider = result.scalar_one_or_none()
    if provider:
        # round to 1 decimal (fits DECIMAL(2,1) in schema)
        provider.avg_rating = round(Decimal(str(avg)), 1) if avg is not None else Decimal("0.0")

async def get_provider_reviews(
    db: AsyncSession,
    provider_id: UUID   
) -> list[Review]:
    result = await db.execute(
        select(Review)
        .options(selectinload(Review.customer))
        .where(Review.provider_id == provider_id)
        .order_by(Review.created_at.desc())
    )
    return result.scalars().all()

async def get_provider_rating_summary(
    db: AsyncSession,
    provider_id: UUID
) -> dict:
    result = await db.execute(
        select(
            func.coalesce(func.avg(Review.rating), 0).label("avg"),
            func.count(Review.id).label("count")
        ).where(Review.provider_id == provider_id)
    )
    row = result.one()
    return{
        "provider_id": provider_id,
        "avg_rating": round(Decimal(str(row.avg)), 1),
        "total_reviews": row.count
    }