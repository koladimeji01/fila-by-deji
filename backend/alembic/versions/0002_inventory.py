"""Add per-size inventory records, initially zero for all existing products.

Revision ID: 0002_inventory
Revises: 0001_initial
"""
from alembic import op
import sqlalchemy as sa

revision = '0002_inventory'
down_revision = '0001_initial'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('product_inventory',
        sa.Column('product_id', sa.String(60), sa.ForeignKey('products.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('size', sa.String(4), primary_key=True),
        sa.Column('quantity', sa.Integer(), nullable=False, server_default='0'),
        sa.CheckConstraint('quantity >= 0', name='ck_inventory_nonnegative_quantity'),
        sa.CheckConstraint("size IN ('32', '35', '39', '41')", name='ck_inventory_valid_size'))
    # Backfill safe zero stock for existing products; real quantities are set explicitly.
    for size in ('32', '35', '39', '41'):
        op.execute(sa.text("INSERT INTO product_inventory (product_id, size, quantity) "
                           "SELECT id, :size, 0 FROM products").bindparams(size=size))


def downgrade():
    op.drop_table('product_inventory')
