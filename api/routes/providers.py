from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from core.enums import ProviderStatus
from db.database import get_db
from models.category import Category
from models.provider import ProviderProfile
from models.service import Service
from models.user import User
from schemas.provider import (
    ProviderRegisterRequest,
    ProviderResponse,
    ProviderDetailResponse,
    ProviderListItem,
    ProviderUpdate,
)
from models.availability import ProviderAvailability
from services.provider_service import register_provider
from core.dependencies import get_current_user, get_admin_user
from core.distance import haversine_km
from datetime import datetime
from typing import List, Optional
from datetime import datetime, time

router = APIRouter(prefix="/providers", tags=["Providers"])

# --- Provider applies to register ---
@router.post("/register", response_model=ProviderResponse)
async def register(
    body:ProviderRegisterRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        provider = await register_provider(current_user, body, db)
        return provider
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
# --- Get own provider profile ---
@router.get("/me", response_model=ProviderResponse)
async def get_my_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(ProviderProfile)
        .options(
            selectinload(ProviderProfile.categories),
            selectinload(ProviderProfile.availability), 
        )
        .where(ProviderProfile.user_id == current_user.id)
    )
    provider = result.scalar_one_or_none()
    if not provider:
       raise HTTPException(status_code=404, detail="Provider profile not found")
    return provider

# --- Edit own provider profile ---
@router.patch("/me", response_model = ProviderResponse)
async def edit_own_provider_profile(
    body: ProviderUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(ProviderProfile).where(ProviderProfile.user_id == current_user.id)
    )
    provider = result.scalar_one_or_none()
    if not provider:
       raise HTTPException(status_code=404, detail="Provider profile not found")
    
    if body.bio is not None:
        provider.bio = body.bio
    if body.profile_photo_url is not None:
        provider.profile_photo_url = body.profile_photo_url
    if body.years_experience is not None:
        provider.years_experience = body.years_experience
    if body.certification is not None:
        provider.certification = body.certification
    if body.certification_url is not None:                  
        provider.certification_url = body.certification_url
    if body.location is not None:
        provider.location = body.location
    if body.latitude is not None:
        provider.latitude = body.latitude
    if body.longitude is not None:
        provider.longitude = body.longitude
    if body.service_radius_km is not None:                
        provider.service_radius_km = body.service_radius_km
    if body.is_available is not None:
        provider.is_available = body.is_available

    # update categories if provided
    if body.category_ids is not None:
        unique_ids = set(body.category_ids)
        result = await db.execute(
            select(Category).where(Category.id.in_(unique_ids))
        )
        categories = result.scalars().all()
        if len(categories) != len(unique_ids):
            raise HTTPException(status_code=400, detail="One or more category IDs are invalid")
        provider.categories = categories

    if body.availability is not None:
        await db.execute(
            delete(ProviderAvailability).where(
                ProviderAvailability.provider_id == provider.id
            )
        )
        for slot in body.availability:
            open_h, open_m = map(int, slot.open_time.split(":"))
            close_h, close_m = map(int, slot.close_time.split(":"))
            availability = ProviderAvailability(
                provider_id=provider.id,
                day_of_week=slot.day_of_week.lower(),
                open_time=time(open_h, open_m),
                close_time=time(close_h, close_m)
            )
            db.add(availability)

    await db.commit()
    await db.refresh(provider)
    await db.refresh(provider, attribute_names=["categories"])
    return provider

# --- Public: browse providers (optionally filter by category, sort by distance) ---
@router.get("", response_model=List[ProviderListItem])
async def list_providers(
    category_id: Optional[str] = Query(default=None),
    customer_lat: Optional[float] = Query(default=None, ge=-90, le=90),
    customer_lng: Optional[float] = Query(default=None, ge=-180, le=180),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(ProviderProfile)
        .options(
            selectinload(ProviderProfile.user),
            selectinload(ProviderProfile.categories),
        )
        .where(ProviderProfile.status == ProviderStatus.approved.value)
    )
    if category_id:
        query = query.where(
            ProviderProfile.categories.any(Category.id == category_id)
        )

    # Cap upstream pull so distance sort can happen in Python without
    # unbounded memory. Move to DB-side haversine (PostGIS / cube_earthdistance)
    # when this becomes a bottleneck.
    query = query.limit(500)

    result = await db.execute(query)
    providers = result.scalars().all()

    items = []
    for p in providers:
        distance_km = haversine_km(
            customer_lat, customer_lng, p.latitude, p.longitude
        )
        items.append({
            "id": p.id,
            "user_id": p.user_id,
            "name": p.user.name if p.user else None,
            "bio": p.bio,
            "profile_photo_url": p.profile_photo_url,
            "location": p.location,
            "avg_rating": float(p.avg_rating or 0),
            "is_available": p.is_available,
            "service_radius_km": p.service_radius_km,
            "distance_km": distance_km,
            "categories": p.categories,
            "_created_at": p.created_at,
        })

    if customer_lat is not None and customer_lng is not None:
        items.sort(key=lambda x: (
            x["distance_km"] is None,
            x["distance_km"] if x["distance_km"] is not None else 0,
        ))
    else:
        items.sort(
            key=lambda x: (-x["avg_rating"], -x["_created_at"].timestamp())
        )

    for item in items:
        item.pop("_created_at", None)

    return items[offset:offset + limit]


# --- View provider public profile ---
@router.get("/{provider_id}", response_model=ProviderDetailResponse)
async def get_provider_profile(
    provider_id: str,
    customer_lat: Optional[float] = Query(default=None, ge=-90, le=90),
    customer_lng: Optional[float] = Query(default=None, ge=-180, le=180),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(ProviderProfile)
        .options(
            selectinload(ProviderProfile.user),
            selectinload(ProviderProfile.availability),
            selectinload(ProviderProfile.categories),
        )
        .where(
            ProviderProfile.id == provider_id,
            ProviderProfile.status == ProviderStatus.approved.value,
        )
    )
    provider = result.scalar_one_or_none()

    if not provider:
        raise HTTPException(status_code=404, detail="Provider profile not found")

    services_result = await db.execute(
        select(Service).where(
            Service.provider_id == provider.id,
            Service.is_active == True,  # noqa: E712
        )
    )
    services = services_result.scalars().all()

    distance_km = haversine_km(
        customer_lat, customer_lng, provider.latitude, provider.longitude
    )

    return {
        "id": provider.id,
        "user_id": provider.user_id,
        "name": provider.user.name if provider.user else None,
        "bio": provider.bio,
        "profile_photo_url": provider.profile_photo_url,
        "years_experience": provider.years_experience,
        "certification": provider.certification,
        "certification_url": provider.certification_url,
        "location": provider.location,
        "latitude": float(provider.latitude) if provider.latitude is not None else None,
        "longitude": float(provider.longitude) if provider.longitude is not None else None,
        "service_radius_km": provider.service_radius_km,
        "avg_rating": float(provider.avg_rating or 0),
        "is_available": provider.is_available,
        "status": provider.status,
        "created_at": provider.created_at,
        "distance_km": distance_km,
        "availability": provider.availability,
        "services": services,
        "categories": provider.categories,
    }
