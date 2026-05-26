"""add dispute image urls

Revision ID: d5e6f7a8b9c0
Revises: c4f8a2d19b30
Create Date: 2026-05-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'd5e6f7a8b9c0'
down_revision: Union[str, Sequence[str], None] = 'c4f8a2d19b30'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('disputes', sa.Column('reason_image_urls', postgresql.ARRAY(sa.Text()), server_default='{}', nullable=False))
    op.add_column('disputes', sa.Column('provider_response_image_urls', postgresql.ARRAY(sa.Text()), server_default='{}', nullable=False))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('disputes', 'provider_response_image_urls')
    op.drop_column('disputes', 'reason_image_urls')
