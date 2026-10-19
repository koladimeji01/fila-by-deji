"""Initial customer accounts, catalog and draft orders.

Revision ID: 0001_initial
Revises:
"""
from alembic import op
import sqlalchemy as sa

revision = '0001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('users',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('email', sa.String(254), nullable=False),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False))
    op.create_index('ix_users_email', 'users', ['email'], unique=True)
    op.create_table('products',
        sa.Column('id', sa.String(60), primary_key=True),
        sa.Column('name', sa.String(150), nullable=False),
        sa.Column('category', sa.String(50), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('price_kobo', sa.Integer(), nullable=False),
        sa.Column('image_url', sa.String(300), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.CheckConstraint('price_kobo > 0', name='ck_product_positive_price'))
    op.create_table('orders',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('status', sa.String(30), nullable=False),
        sa.Column('total_kobo', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('total_kobo >= 0', name='ck_order_nonnegative_total'))
    op.create_index('ix_orders_user_id', 'orders', ['user_id'])
    op.create_table('order_items',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('order_id', sa.String(36), sa.ForeignKey('orders.id', ondelete='CASCADE'), nullable=False),
        sa.Column('product_id', sa.String(60), sa.ForeignKey('products.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('product_name', sa.String(150), nullable=False),
        sa.Column('size', sa.String(4), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('unit_price_kobo', sa.Integer(), nullable=False),
        sa.CheckConstraint('quantity > 0', name='ck_order_item_positive_quantity'),
        sa.CheckConstraint('unit_price_kobo > 0', name='ck_order_item_positive_price'))


def downgrade():
    op.drop_table('order_items')
    op.drop_index('ix_orders_user_id', table_name='orders')
    op.drop_table('orders')
    op.drop_table('products')
    op.drop_index('ix_users_email', table_name='users')
    op.drop_table('users')
