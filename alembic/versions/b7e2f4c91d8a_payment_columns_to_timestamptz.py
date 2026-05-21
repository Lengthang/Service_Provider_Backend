"""naive datetime columns to timestamptz

Revision ID: b7e2f4c91d8a
Revises: 9ec06a435371
Create Date: 2026-05-04 22:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b7e2f4c91d8a'
down_revision: Union[str, Sequence[str], None] = '9ec06a435371'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (table, column) pairs whose existing TIMESTAMP WITHOUT TIME ZONE values
# represent UTC and should be migrated to TIMESTAMP WITH TIME ZONE.
# Tables already using timestamptz (users, provider_profiles, bookings,
# booking_status_history) are intentionally omitted.
_COLUMNS = [
    ("categories", "created_at"),
    ("saved_payment_methods", "created_at"),
    ("wallets", "created_at"),
    ("portfolio_items", "created_at"),
    ("services", "created_at"),
    ("wallet_transactions", "created_at"),
    ("withdrawal_requests", "created_at"),
    ("promo_codes", "expires_at"),
    ("promo_codes", "created_at"),
    ("promo_redemptions", "redeemed_at"),
    ("escrow_accounts", "released_at"),
    ("escrow_accounts", "created_at"),
    ("booking_confirmations", "provider_confirmed_at"),
    ("booking_confirmations", "customer_confirmed_at"),
    ("booking_confirmations", "auto_release_at"),
    ("booking_confirmations", "created_at"),
    ("disputes", "resolved_at"),
    ("disputes", "created_at"),
    ("payments", "paid_at"),
    ("payments", "created_at"),
    ("reviews", "created_at"),
]


def upgrade() -> None:
    for table, column in _COLUMNS:
        op.execute(
            f'ALTER TABLE {table} '
            f'ALTER COLUMN {column} TYPE TIMESTAMP WITH TIME ZONE '
            f'USING {column} AT TIME ZONE \'UTC\''
        )


def downgrade() -> None:
    for table, column in reversed(_COLUMNS):
        op.execute(
            f'ALTER TABLE {table} '
            f'ALTER COLUMN {column} TYPE TIMESTAMP WITHOUT TIME ZONE '
            f'USING {column} AT TIME ZONE \'UTC\''
        )
