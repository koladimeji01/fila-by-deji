"""Store per-user read acknowledgements for computed admin notifications.

Revision ID: 0012_staff_notifications
Revises: 0011_inventory_audit
"""
from alembic import op
import sqlalchemy as sa

revision = '0012_staff_notifications'
down_revision = '0011_inventory_audit'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'staff_notification_reads',
        sa.Column('staff_user_id', sa.String(36),
                  sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('notification_key', sa.String(140), primary_key=True),
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=False),
    )
    if op.get_bind().dialect.name == 'postgresql':
        op.execute('ALTER TABLE public.staff_notification_reads ENABLE ROW LEVEL SECURITY')
        op.execute('REVOKE ALL ON public.staff_notification_reads FROM anon, authenticated')


def downgrade():
    op.drop_table('staff_notification_reads')
