"""Audit manual changes to cap inventory, without recording customer hold movements.

Revision ID: 0011_inventory_audit
Revises: 0010_enquiry_followup
"""
from alembic import op
import sqlalchemy as sa

revision = '0011_inventory_audit'
down_revision = '0010_enquiry_followup'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'inventory_change_audit',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('product_id', sa.String(60),
                  sa.ForeignKey('products.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('size', sa.String(4), nullable=False),
        sa.Column('previous_quantity', sa.Integer, nullable=False),
        sa.Column('new_quantity', sa.Integer, nullable=False),
        sa.Column('reason', sa.String(16), nullable=False),
        sa.Column('changed_by', sa.String(36),
                  sa.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('changed_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("size IN ('32','35','39','41')", name='ck_inventory_audit_size'),
        sa.CheckConstraint("reason IN ('restock','correction','damage','other')",
                           name='ck_inventory_audit_reason'),
        sa.CheckConstraint("previous_quantity >= 0 AND new_quantity >= 0",
                           name='ck_inventory_audit_nonnegative'),
    )
    op.create_index('ix_inventory_change_audit_product_id', 'inventory_change_audit', ['product_id'])
    op.create_index('ix_inventory_change_audit_changed_at', 'inventory_change_audit', ['changed_at'])
    if op.get_bind().dialect.name == 'postgresql':
        op.execute('ALTER TABLE public.inventory_change_audit ENABLE ROW LEVEL SECURITY')
        op.execute('REVOKE ALL ON public.inventory_change_audit FROM anon, authenticated')


def downgrade():
    op.drop_index('ix_inventory_change_audit_changed_at', table_name='inventory_change_audit')
    op.drop_index('ix_inventory_change_audit_product_id', table_name='inventory_change_audit')
    op.drop_table('inventory_change_audit')
