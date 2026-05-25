"""add updated_at to services

Revision ID: e7a1b2c3d4e5
Revises: 8062778b686e
Create Date: 2026-05-25 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e7a1b2c3d4e5'
down_revision: Union[str, Sequence[str], None] = '8062778b686e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'services',
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    )
    # Backfill existing rows so "Updated …" has a sensible value from the start.
    # New writes set updated_at via the model's onupdate/default.
    op.execute('UPDATE services SET updated_at = created_at WHERE updated_at IS NULL')


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('services', 'updated_at')
