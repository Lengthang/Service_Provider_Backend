from sqlalchemy import Column, ForeignKey, Table
from sqlalchemy.dialects.postgresql import UUID
from db.database import Base

# Association table for the many-to-many relationship
provider_categories = Table(
    "provider_categories",
    Base.metadata,
    Column("provider_id", UUID(as_uuid=True),
           ForeignKey("provider_profiles.id", ondelete="CASCADE"), primary_key=True),
    Column("category_id", UUID(as_uuid=True),
           ForeignKey("categories.id", ondelete="CASCADE"), primary_key=True),
)