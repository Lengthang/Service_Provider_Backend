"""add category_id, image_url, min_quantity to services

Revision ID: c1d2a3b4e5f6
Revises: f6641cde9e0d
Create Date: 2026-05-06 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1d2a3b4e5f6'
down_revision: Union[str, Sequence[str], None] = 'f6641cde9e0d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'services',
        sa.Column('category_id', sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        op.f('services_category_id_fkey'),
        'services', 'categories',
        ['category_id'], ['id'],
        ondelete='RESTRICT',
    )
    op.add_column(
        'services',
        sa.Column('image_url', sa.Text(), nullable=True),
    )
    op.add_column(
        'services',
        sa.Column(
            'min_quantity',
            sa.Integer(),
            nullable=False,
            server_default=sa.text('1'),
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('services', 'min_quantity')
    op.drop_column('services', 'image_url')
    op.drop_constraint(
        op.f('services_category_id_fkey'), 'services', type_='foreignkey'
    )
    op.drop_column('services', 'category_id')
