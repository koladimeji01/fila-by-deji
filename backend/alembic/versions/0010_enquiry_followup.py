"""Keep private enquiry follow-up separate from order/payment lifecycle.

Revision ID: 0010_enquiry_followup
Revises: 0009_staff_manager
"""
from alembic import op
import sqlalchemy as sa

revision = '0010_enquiry_followup'
down_revision = '0009_staff_manager'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'enquiry_followups',
        sa.Column('order_id', sa.String(36),
                  sa.ForeignKey('orders.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('stage', sa.String(20), nullable=False),
        sa.Column('internal_note', sa.Text(), nullable=False),
        sa.Column('updated_by', sa.String(36),
                  sa.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "stage IN ('new','contacted','awaiting_reply','closed')",
            name='ck_enquiry_followup_stage'),
    )
    if op.get_bind().dialect.name == 'postgresql':
        op.execute('ALTER TABLE public.enquiry_followups ENABLE ROW LEVEL SECURITY')
        op.execute('REVOKE ALL ON public.enquiry_followups FROM anon, authenticated')


def downgrade():
    op.drop_table('enquiry_followups')
