"""multi-service booking: booking_items table, booking amount columns

Revision ID: d2e3f4a5b6c7
Revises: c1d2a3b4e5f6
Create Date: 2026-05-06 00:30:00.000000

Drops bookings.service_id and replaces single-service booking with a
booking_items child table. Migration assumes a fresh / empty bookings
table — no backfill is performed.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd2e3f4a5b6c7'
down_revision: Union[str, Sequence[str], None] = 'c1d2a3b4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'booking_items',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('booking_id', sa.UUID(), nullable=False),
        sa.Column('service_id', sa.UUID(), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('unit_price_at_booking', sa.Numeric(10, 2), nullable=False),
        sa.Column('line_total_at_booking', sa.Numeric(10, 2), nullable=False),
        sa.Column(
            'created_at', sa.DateTime(timezone=True),
            server_default=sa.text('now()'), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ['booking_id'], ['bookings.id'], ondelete='CASCADE'
        ),
        sa.ForeignKeyConstraint(
            ['service_id'], ['services.id'], ondelete='RESTRICT'
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint(
            'quantity >= 1', name='ck_booking_items_quantity_positive'
        ),
    )
    op.create_index(
        'ix_booking_items_booking_id', 'booking_items', ['booking_id']
    )

    op.add_column(
        'bookings',
        sa.Column('subtotal', sa.Numeric(10, 2), nullable=False),
    )
    op.add_column(
        'bookings',
        sa.Column(
            'discount_amount', sa.Numeric(10, 2),
            nullable=False, server_default=sa.text('0'),
        ),
    )
    op.add_column(
        'bookings',
        sa.Column('total_amount', sa.Numeric(10, 2), nullable=False),
    )

    op.drop_constraint(
        op.f('bookings_service_id_fkey'), 'bookings', type_='foreignkey'
    )
    op.drop_column('bookings', 'service_id')


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column(
        'bookings',
        sa.Column('service_id', sa.UUID(), nullable=False),
    )
    op.create_foreign_key(
        op.f('bookings_service_id_fkey'),
        'bookings', 'services',
        ['service_id'], ['id'],
    )
    op.drop_column('bookings', 'total_amount')
    op.drop_column('bookings', 'discount_amount')
    op.drop_column('bookings', 'subtotal')
    op.drop_index('ix_booking_items_booking_id', table_name='booking_items')
    op.drop_table('booking_items')
