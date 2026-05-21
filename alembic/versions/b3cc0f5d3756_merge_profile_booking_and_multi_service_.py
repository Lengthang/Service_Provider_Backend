"""merge profile/booking and multi-service branches

Revision ID: b3cc0f5d3756
Revises: 95f3382b25cd, d2e3f4a5b6c7
Create Date: 2026-05-06 19:49:48.552752

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b3cc0f5d3756'
down_revision: Union[str, Sequence[str], None] = ('95f3382b25cd', 'd2e3f4a5b6c7')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
