from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from fastapi import HTTPException
from datetime import time

from core.enums import UserRole
from models.provider import ProviderProfile
from models.availability import ProviderAvailability
from models.category import Category
from models.user import User
from schemas.provider import ProviderRegisterRequest


async def register_provider(
    user: User,
    data: ProviderRegisterRequest,
    db: AsyncSession
) -> ProviderProfile:
    result = await db.execute(
        select(ProviderProfile).where(ProviderProfile.user_id == user.id)
    )
    if result.scalar_one_or_none():
        raise ValueError("Provider profile already exists")

    # validate categories exist
    categories = []
    if data.category_ids:
        unique_ids = set(data.category_ids)
        result = await db.execute(
            select(Category).where(Category.id.in_(unique_ids))
        )
        categories = result.scalars().all()
        if len(categories) != len(unique_ids):
            raise HTTPException(status_code=400, detail="One or more category IDs are invalid")

    provider = ProviderProfile(
        user_id=user.id,
        bio=data.bio,
        profile_photo_url=data.profile_photo_url,
        years_experience=data.years_experience,
        certification=data.certification,
        certification_url=data.certification_url,
        national_id_url=data.national_id_url,
        location=data.location,
        latitude=data.latitude,
        longitude=data.longitude,
        service_radius_km=data.service_radius_km,
    )
    provider.categories = categories
    db.add(provider)
    await db.flush()

    for slot in data.availability:
        open_h, open_m = map(int, slot.open_time.split(":"))
        close_h, close_m = map(int, slot.close_time.split(":"))
        db.add(ProviderAvailability(
            provider_id=provider.id,
            day_of_week=slot.day_of_week.lower(),
            open_time=time(open_h, open_m),
            close_time=time(close_h, close_m)
        ))

    user.role = UserRole.provider.value
    await db.commit()
    await db.refresh(provider)
    await db.refresh(provider, attribute_names=["categories"])
    return provider