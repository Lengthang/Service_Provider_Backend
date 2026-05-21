from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List
from db.database import get_db
from models.category import Category
from schemas.category import CategoryCreate, CategoryUpdate, CategoryResponse
from core.dependencies import get_current_user, get_admin_user
from models.user import User

router = APIRouter(prefix="/categories", tags=["Categories"])

# --- Public: anyone can view active categories ---
@router.get('/', response_model=List[CategoryResponse])
async def get_categories(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Category).where(Category.is_active == True)
    )

    return result.scalars().all()

# --- Admin: create a new category ---
@router.post('/', response_model=CategoryResponse)
async def create_category(
    body: CategoryCreate,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    # check for duplicate
    result = await db.execute(
        select(Category).where(Category.name == body.name)
    )
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400,  detail="Category already exists")
    
    category = Category(
        name=body.name, 
        icon_url=body.icon_url
    )
    db.add(category)
    await db.commit()
    await db.refresh(category)
    return category

# --- Admin: update a category ---
@router.patch("/{category_id}", response_model=CategoryResponse)
async def update_category(
    category_id: str,
    body: CategoryUpdate,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Category).where(Category.id == category_id)
    )
    category = result.scalar_one_or_none()
    if not category:
        raise HTTPException(status_code=404,  detail="Category not found")
    
    if body.name is not None:
        category.name = body.name
    if body.icon_url is not None:
        category.icon_url = body.icon_url
    if body.is_active is not None:
        category.is_active = body.is_active
    
    await db.commit()
    await db.refresh(category)
    return category

# --- Admin: delete a category ---
@router.delete("/{category_id}")
async def delete_category(
    category_id: str,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Category).where(Category.id == category_id)
    )
    category = result.scalar_one_or_none()

    if not category:
        raise HTTPException(status_code=404,  detail="Category not found")
    await db.delete(category)
    await db.commit()
    return {"message": "Category deleted"}