from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from typing import List, Optional
from core.enums import ProviderStatus
from db.database import get_db
from models.service import Service
from models.provider import ProviderProfile
from schemas.service import ServiceCreate, ServiceUpdate, ServiceResponse
from core.dependencies import get_current_user
from models.user import User

router = APIRouter(prefix="/services", tags=["Services"])
# Helper — gets the approved provider profile for the current user
async def get_approved_provider(current_user: User, db: AsyncSession) -> ProviderProfile:
    result = await db.execute(
        select(ProviderProfile)
        .options(selectinload(ProviderProfile.categories))
        .where(ProviderProfile.user_id == current_user.id)
    )
    provider = result.scalar_one_or_none()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider profile not found")
    if provider.status != ProviderStatus.approved.value:
        raise HTTPException(status_code=403, detail="Your provider account is not approved yet")
    return provider


def _ensure_category_offered_by_provider(provider: ProviderProfile, category_id: UUID) -> None:
    if not any(c.id == category_id for c in provider.categories):
        raise HTTPException(
            status_code=400,
            detail="Service category must be one of the provider's own categories"
        )



# --- Public: get all services, optionally filter by category ---
@router.get("/", response_model=List[ServiceResponse])
async def get_services(
    category_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db)
):
    query = select(Service).where(Service.is_active == True)  # noqa: E712
    if category_id is not None:
        query = query.where(Service.category_id == category_id)

    result = await db.execute(query)
    return result.scalars().all()
    
# --- Public: get all services for a specific provider ---
@router.get("/providers/{provider_id}", response_model=List[ServiceResponse])
async def get_provider_services(
    provider_id: str,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Service).where(Service.is_active == True, Service.provider_id == provider_id)
    )

    return result.scalars().all()

# --- Provider: add a new service ---
@router.post("/", response_model=ServiceResponse)
async def create_service(
    body:ServiceCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    provider = await get_approved_provider(current_user, db)
    _ensure_category_offered_by_provider(provider, body.category_id)

    service = Service(
        provider_id=provider.id,
        category_id=body.category_id,
        title=body.title,
        description=body.description,
        image_url=body.image_url,
        price=body.price,
        duration_minutes=body.duration_minutes,
        min_quantity=body.min_quantity,
    )
    db.add(service)
    await db.commit()
    await db.refresh(service)
    return service

# --- Provider: update their own service ---
@router.patch("/{service_id}", response_model=ServiceResponse)
async def update_service(
    service_id: str,
    body: ServiceUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    provider = await get_approved_provider(current_user, db)

    result = await db.execute(
        select(Service).where(Service.id == service_id)
    )

    service = result.scalar_one_or_none()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    # Make sure the provider owns this service
    if provider.id != service.provider_id:
        raise HTTPException(status_code=403, detail="You do not own this service")
    
    if body.category_id is not None:
        _ensure_category_offered_by_provider(provider, body.category_id)
        service.category_id = body.category_id
    if body.title is not None:
        service.title = body.title
    if body.description is not None:
        service.description = body.description
    if body.image_url is not None:
        service.image_url = body.image_url
    if body.price is not None:
        service.price = body.price
    if body.duration_minutes is not None:
        service.duration_minutes = body.duration_minutes
    if body.min_quantity is not None:
        service.min_quantity = body.min_quantity
    if body.is_active is not None:
        service.is_active = body.is_active

    await db.commit()
    await db.refresh(service)
    return service

# --- Provider: deactivate their own service (soft delete) ---
# Hard-deleting would fail under booking_items.service_id (RESTRICT) once any
# booking references the service, and would also erase historical line items.
@router.delete("/{service_id}")
async def delete_service(
    service_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    provider = await get_approved_provider(current_user, db)
    result = await db.execute(
        select(Service).where(Service.id == service_id)
    )
    service = result.scalar_one_or_none()

    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    if service.provider_id != provider.id:
        raise HTTPException(status_code=403, detail="You do not own this service")

    service.is_active = False
    await db.commit()
    return {"message": "Service deactivated"}

@router.get("/mine", response_model=List[ServiceResponse])
async def get_my_services(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    provider = await get_approved_provider(current_user, db)
    result = await db.execute(
        select(Service)
        .where(Service.provider_id == provider.id)   # no is_active filter
        .order_by(Service.created_at.desc())
    )
    return result.scalars().all()
