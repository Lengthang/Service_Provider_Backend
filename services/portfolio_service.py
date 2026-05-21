from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from fastapi import HTTPException

from models.portfolio import PortfolioItem
from models.provider import ProviderProfile
from models.user import User
from schemas.portfolio import PortfolioItemCreate, PortfolioItemUpdate

async def _get_current_provider_profile(
    db: AsyncSession,
    user: User
) -> ProviderProfile:
    """Return the provider profile owned by the current user, or 403"""
    result = await db.execute(
        select(ProviderProfile).where(
            ProviderProfile.user_id == user.id
        )
    )
    provider = result.scalar_one_or_none()
    if not provider:
        raise HTTPException(status_code=403, detail="Only providers can manage portfolio items")
    return provider

async def create_portfolio_item(
    db: AsyncSession,
    user: User,
    data: PortfolioItemCreate
) -> PortfolioItem:
    provider = await _get_current_provider_profile(db, user)

    item = PortfolioItem(
        provider_id=provider.id,
        before_photo_url=data.before_photo_url,
        after_photo_url=data.after_photo_url,
        caption=data.caption
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item

async def list_provider_portfolio(
    db: AsyncSession, 
    provider_id: UUID
) -> list[PortfolioItem]:
    result = await db.execute(
        select(PortfolioItem)
        .where(PortfolioItem.provider_id == provider_id)
        .order_by(PortfolioItem.created_at.desc())
    )
    return result.scalars().all()

async def list_my_portfolio(
    db: AsyncSession,
    user: User
) -> list[PortfolioItem]:
    provider = await _get_current_provider_profile(db, user)
    return await list_provider_portfolio(db, provider.id)
        
async def update_portfolio_item(
    db: AsyncSession,
    user: User,
    item_id: UUID,
    data: PortfolioItemUpdate
) -> PortfolioItem:
    provider = await _get_current_provider_profile(db, user)

    result = await db.execute(
        select(PortfolioItem).where(PortfolioItem.id == item_id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Portfolio item not found")
    if str(item.provider_id) != str(provider.id):
        raise HTTPException(status_code=403, detail="Not your portfolio item")
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(item, field, value)

    await db.commit()
    await db.refresh(item)
    return item


async def delete_portfolio_item(
    db: AsyncSession, user: User, item_id: UUID
) -> None:
    provider = await _get_current_provider_profile(db, user)

    result = await db.execute(
        select(PortfolioItem).where(PortfolioItem.id == item_id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Portfolio item not found")
    if str(item.provider_id) != str(provider.id):
        raise HTTPException(status_code=403, detail="Not your portfolio item")

    await db.delete(item)
    await db.commit()

