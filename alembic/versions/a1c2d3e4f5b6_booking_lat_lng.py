"""add latitude and longitude to bookings

Revision ID: a1c2d3e4f5b6
Revises: f6641cde9e0d
Create Date: 2026-05-05 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1c2d3e4f5b6'
down_revision: Union[str, Sequence[str], None] = 'f6641cde9e0d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('bookings', sa.Column('latitude', sa.Numeric(precision=9, scale=6), nullable=True))
    op.add_column('bookings', sa.Column('longitude', sa.Numeric(precision=9, scale=6), nullable=True))


def downgrade() -> None:
    op.drop_column('bookings', 'longitude')
    op.drop_column('bookings', 'latitude')
