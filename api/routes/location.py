from uuid import UUID
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from db.database import get_db
from models.user import User
from models.location import SavedLocation
from schemas.location import (
    SavedLocationCreate,
    SavedLocationUpdate,
    SavedLocationResponse,
)
from core.dependencies import get_current_user

# A customer can save service locations ("Home", "Office", …) and pick one when
# booking instead of using their device's current GPS fix. Exactly one location
# can be the default; setting a new default clears the previous one.
router = APIRouter(prefix="/customer/locations", tags=["Saved Locations"])


async def _get_owned_location(
    location_id: UUID, me: User, db: AsyncSession
) -> SavedLocation:
    result = await db.execute(
        select(SavedLocation).where(
            SavedLocation.id == location_id,
            SavedLocation.user_id == me.id,
        )
    )
    loc = result.scalar_one_or_none()
    if not loc:
        raise HTTPException(status_code=404, detail="Saved location not found")
    return loc


async def _clear_other_defaults(db: AsyncSession, user_id: UUID, keep_id: UUID | None = None):
    """Unset is_default on all of the user's locations except keep_id."""
    stmt = (
        update(SavedLocation)
        .where(SavedLocation.user_id == user_id, SavedLocation.is_default.is_(True))
        .values(is_default=False)
        .execution_options(synchronize_session=False)
    )
    if keep_id is not None:
        stmt = stmt.where(SavedLocation.id != keep_id)
    await db.execute(stmt)


@router.post("", response_model=SavedLocationResponse, status_code=201)
async def create_location(
    body: SavedLocationCreate,
    me: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # The first location a customer saves becomes their default automatically.
    has_existing = await db.scalar(
        select(SavedLocation.id).where(SavedLocation.user_id == me.id).limit(1)
    )
    make_default = body.is_default or has_existing is None
    if make_default:
        await _clear_other_defaults(db, me.id)

    loc = SavedLocation(
        user_id=me.id,
        label=body.label,
        latitude=body.latitude,
        longitude=body.longitude,
        address=body.address,
        is_default=make_default,
    )
    db.add(loc)
    await db.commit()
    await db.refresh(loc)
    return loc


@router.get("", response_model=List[SavedLocationResponse])
async def list_locations(
    me: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SavedLocation)
        .where(SavedLocation.user_id == me.id)
        .order_by(SavedLocation.is_default.desc(), SavedLocation.created_at)
    )
    return result.scalars().all()


@router.get("/{location_id}", response_model=SavedLocationResponse)
async def get_location(
    location_id: UUID,
    me: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _get_owned_location(location_id, me, db)


@router.patch("/{location_id}", response_model=SavedLocationResponse)
async def update_location(
    location_id: UUID,
    body: SavedLocationUpdate,
    me: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    loc = await _get_owned_location(location_id, me, db)

    if body.label is not None:
        loc.label = body.label
    if body.latitude is not None:
        loc.latitude = body.latitude
    if body.longitude is not None:
        loc.longitude = body.longitude
    if body.address is not None:
        loc.address = body.address
    if body.is_default is not None:
        if body.is_default:
            await _clear_other_defaults(db, me.id, keep_id=loc.id)
            loc.is_default = True
        else:
            loc.is_default = False

    await db.commit()
    await db.refresh(loc)
    return loc


@router.delete("/{location_id}", status_code=204)
async def delete_location(
    location_id: UUID,
    me: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    loc = await _get_owned_location(location_id, me, db)
    await db.delete(loc)
    await db.commit()
