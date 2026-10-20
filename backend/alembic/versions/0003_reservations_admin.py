"""Admin role and time-limited stock holds; existing orders remain drafts.

Revision ID: 0003_holds
Revises: 0002_inventory
"""
from alembic import op
import sqlalchemy as sa

revision = '0003_holds'
down_revision = '0002_inventory'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('is_admin', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('orders', sa.Column('reserved_until', sa.DateTime(timezone=True), nullable=True))
    op.create_index('ix_orders_status_reserved_until', 'orders', ['status', 'reserved_until'])


def downgrade():
    op.drop_index('ix_orders_status_reserved_until', table_name='orders')
    op.drop_column('orders', 'reserved_until')
    op.drop_column('users', 'is_admin')
