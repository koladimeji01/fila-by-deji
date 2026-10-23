"""Unpaid checkout request references and customer delivery region.
Revision ID: 0005_order_requests
Revises: 0004_saved_items
"""
from alembic import op
import sqlalchemy as sa

revision = '0005_order_requests'
down_revision = '0004_saved_items'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('orders', sa.Column('client_request_id', sa.String(36), nullable=True))
    op.add_column('orders', sa.Column('delivery_destination', sa.String(120), nullable=True))
    op.create_index('ix_orders_client_request_id', 'orders', ['client_request_id'], unique=True)


def downgrade():
    op.drop_index('ix_orders_client_request_id', table_name='orders')
    op.drop_column('orders', 'delivery_destination')
    op.drop_column('orders', 'client_request_id')
