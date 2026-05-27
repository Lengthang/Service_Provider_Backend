"""add promo card copy fields

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-05-27 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f2a3b4c5d6e7'
down_revision: Union[str, Sequence[str], None] = 'e1f2a3b4c5d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('promo_codes', sa.Column('title', sa.String(length=60), nullable=True))
    op.add_column('promo_codes', sa.Column('headline', sa.String(length=120), nullable=True))
    op.add_column('promo_codes', sa.Column('subtitle', sa.String(length=160), nullable=True))
    op.add_column('promo_codes', sa.Column('cta_label', sa.String(length=40), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('promo_codes', 'cta_label')
    op.drop_column('promo_codes', 'subtitle')
    op.drop_column('promo_codes', 'headline')
    op.drop_column('promo_codes', 'title')
