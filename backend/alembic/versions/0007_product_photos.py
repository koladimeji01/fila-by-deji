"""Store optimized admin product photos behind the FastAPI image route.

Revision ID: 0007_product_photos
Revises: 0006_delivery_quotes
"""
from alembic import op
import sqlalchemy as sa

revision = '0007_product_photos'
down_revision = '0006_delivery_quotes'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'product_photos',
        sa.Column('product_id', sa.String(60),
                  sa.ForeignKey('products.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('image_data', sa.LargeBinary(), nullable=False),
        sa.Column('mime_type', sa.String(32), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    if op.get_bind().dialect.name == 'postgresql':
        op.execute('ALTER TABLE public.product_photos ENABLE ROW LEVEL SECURITY')
        op.execute('REVOKE ALL ON public.product_photos FROM anon, authenticated')


def downgrade():
    op.drop_table('product_photos')
