from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List

from  db.database import get_db
from core.dependencies import get_current_user, get_admin_user
from models.user import User
from models.dispute import Dispute
from schemas.dispute import DisputeCreate, DisputeOut, DisputeResolve
from services.dispute_service import create_dispute, resolve_dispute

router = APIRouter(prefix="/disputes", tags=["Disputes"])

@router.post("/", response_model=DisputeOut, status_code=201)
async def raise_dispute(
    data: DisputeCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    return await create_dispute(db, user, data)


@router.get("/my", response_model=List[DisputeOut])
async def my_disputes(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Dispute).where(Dispute.raised_by == user.id)
        .order_by(Dispute.created_at.desc())
    )
    return result.scalars().all()


@router.get("/{dispute_id}", response_model=DisputeOut)
async def get_dispute(
    dispute_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Dispute).where(Dispute.id == dispute_id))
    dispute = result.scalar_one_or_none()
    if not dispute:
        raise HTTPException(status_code=404, detail="Dispute not found")
    return dispute


# ── Admin only ──
@router.get("/", response_model=List[DisputeOut])
async def list_all_disputes(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Dispute).order_by(Dispute.created_at.desc())
    )
    return result.scalars().all()


@router.patch("/{dispute_id}/resolve", response_model=DisputeOut)
async def resolve(
    dispute_id: UUID,
    data: DisputeResolve,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    return await resolve_dispute(db, admin, dispute_id, data)