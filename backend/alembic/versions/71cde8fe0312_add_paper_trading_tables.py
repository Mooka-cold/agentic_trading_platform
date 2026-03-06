"""add_paper_trading_tables

Revision ID: 71cde8fe0312
Revises: 274e2ab26b71
Create Date: 2026-02-28 04:58:26.813939

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '71cde8fe0312'
down_revision: Union[str, None] = '274e2ab26b71'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Virtual Accounts -> paper_accounts
    op.create_table(
        'paper_accounts',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('balance', sa.Numeric(precision=20, scale=8), nullable=False, default=100000.0),
        sa.Column('currency', sa.String(length=10), nullable=False, default='USDT'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # 2. Positions -> paper_positions
    op.create_table(
        'paper_positions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('account_id', sa.UUID(), nullable=False),
        sa.Column('symbol', sa.String(length=20), nullable=False),
        sa.Column('side', sa.String(length=10), nullable=False), # LONG/SHORT
        sa.Column('entry_price', sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column('size', sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column('stop_loss', sa.Numeric(precision=20, scale=8), nullable=True),
        sa.Column('take_profit', sa.Numeric(precision=20, scale=8), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, default='OPEN'), # OPEN, CLOSED
        sa.Column('pnl', sa.Numeric(precision=20, scale=8), nullable=True),
        sa.Column('opened_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['account_id'], ['paper_accounts.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # 3. Orders -> paper_orders
    op.create_table(
        'paper_orders',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('account_id', sa.UUID(), nullable=False),
        sa.Column('symbol', sa.String(length=20), nullable=False),
        sa.Column('side', sa.String(length=10), nullable=False), # BUY/SELL
        sa.Column('type', sa.String(length=10), nullable=False), # MARKET/LIMIT
        sa.Column('price', sa.Numeric(precision=20, scale=8), nullable=True),
        sa.Column('quantity', sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, default='PENDING'), # PENDING, FILLED, REJECTED, CANCELED
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('filled_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['account_id'], ['paper_accounts.id'], ),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('paper_orders')
    op.drop_table('paper_positions')
    op.drop_table('paper_accounts')
