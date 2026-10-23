"""Customer saved cap selections, independent of drafts and inventory holds.

Revision ID: 0004_saved_items
Revises: 0003_holds
"""
from alembic import op
import sqlalchemy as sa

revision = '0004_saved_items'
down_revision = '0003_holds'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'saved_items',
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('product_id', sa.String(60), sa.ForeignKey('products.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('size', sa.String(4), primary_key=True),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("size IN ('32','35','39','41')", name='ck_saved_item_size'),
        sa.CheckConstraint('quantity BETWEEN 1 AND 10', name='ck_saved_item_quantity'),
    )
    if op.get_bind().dialect.name == 'postgresql':
        # This app uses its own FastAPI JWT and server-side PostgreSQL role.
        # Supabase Data API clients must NEVER read or write private wishlists.
        op.execute('ALTER TABLE public.saved_items ENABLE ROW LEVEL SECURITY')
        op.execute('REVOKE ALL ON TABLE public.saved_items FROM anon, authenticated')


def downgrade():
    op.drop_table('saved_items')
