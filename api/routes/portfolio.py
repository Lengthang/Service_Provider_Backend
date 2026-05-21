from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from db.database import get_db
from core.dependencies import get_current_user
from models.user import User
from schemas.portfolio import (
    PortfolioItemCreate, PortfolioItemUpdate, PortfolioItemOut
)
from services.portfolio_service import (
    create_portfolio_item,
    list_provider_portfolio,
    list_my_portfolio,
    update_portfolio_item,
    delete_portfolio_item,
)

router = APIRouter(prefix="/portfolio", tags=["Portfolio"])


# ── Provider: manage own portfolio ──
@router.post("/", response_model=PortfolioItemOut, status_code=201)
async def add_item(
    data: PortfolioItemCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    return await create_portfolio_item(db, user, data)


@router.get("/my", response_model=List[PortfolioItemOut])
async def my_portfolio(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    return await list_my_portfolio(db, user)


@router.patch("/{item_id}", response_model=PortfolioItemOut)
async def edit_item(
    item_id: UUID,
    data: PortfolioItemUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    return await update_portfolio_item(db, user, item_id, data)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_item(
    item_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    await delete_portfolio_item(db, user, item_id)


# ── Public: view any provider's portfolio ──
@router.get("/providers/{provider_id}", response_model=List[PortfolioItemOut])
async def public_provider_portfolio(
    provider_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    return await list_provider_portfolio(db, provider_id)