"""Order shipping quotes and immutable admin audit trail.
Revision ID: 0006_delivery_quotes
Revises: 0005_order_requests
"""
from alembic import op
import sqlalchemy as sa

revision = '0006_delivery_quotes'
down_revision = '0005_order_requests'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('orders', sa.Column('shipping_quote_kobo', sa.Integer(), nullable=True))
    op.add_column('orders', sa.Column('shipping_quoted_at', sa.DateTime(timezone=True), nullable=True))
    op.create_check_constraint('ck_orders_nonnegative_shipping_quote', 'orders', 'shipping_quote_kobo IS NULL OR shipping_quote_kobo >= 0')
    op.create_table(
        'delivery_quote_audit',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('order_id', sa.String(36), sa.ForeignKey('orders.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('admin_user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('previous_amount_kobo', sa.Integer(), nullable=True),
        sa.Column('new_amount_kobo', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('new_amount_kobo >= 0', name='ck_delivery_quote_audit_amount'),
    )
    op.create_index('ix_delivery_quote_audit_order_id', 'delivery_quote_audit', ['order_id'])
    if op.get_bind().dialect.name == 'postgresql':
        op.execute('ALTER TABLE public.delivery_quote_audit ENABLE ROW LEVEL SECURITY')
        op.execute('REVOKE ALL ON public.delivery_quote_audit FROM anon, authenticated')


def downgrade():
    op.drop_index('ix_delivery_quote_audit_order_id', table_name='delivery_quote_audit')
    op.drop_table('delivery_quote_audit')
    op.drop_constraint('ck_orders_nonnegative_shipping_quote', 'orders', type_='check')
    op.drop_column('orders', 'shipping_quoted_at')
    op.drop_column('orders', 'shipping_quote_kobo')
