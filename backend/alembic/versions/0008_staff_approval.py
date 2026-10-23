"""Admin-only staff approval queue and immutable approval audit.

Revision ID: 0008_staff_approval
Revises: 0007_product_photos
"""
from alembic import op
import sqlalchemy as sa

revision = '0008_staff_approval'
down_revision = '0007_product_photos'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'staff_applications',
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('status', sa.String(16), nullable=False),
        sa.Column('requested_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('reviewed_by', sa.String(36), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.CheckConstraint("status IN ('pending','approved','rejected','revoked')",
                           name='ck_staff_application_status'),
    )
    op.create_index('ix_staff_applications_status', 'staff_applications', ['status'])
    op.create_table(
        'staff_access_audit',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('subject_user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('actor_user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('action', sa.String(16), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("action IN ('approved','rejected','revoked')", name='ck_staff_audit_action'),
    )
    op.create_index('ix_staff_access_audit_subject', 'staff_access_audit', ['subject_user_id'])
    if op.get_bind().dialect.name == 'postgresql':
        for table in ('staff_applications', 'staff_access_audit'):
            op.execute(f'ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY')
            op.execute(f'REVOKE ALL ON public.{table} FROM anon, authenticated')


def downgrade():
    op.drop_index('ix_staff_access_audit_subject', table_name='staff_access_audit')
    op.drop_table('staff_access_audit')
    op.drop_index('ix_staff_applications_status', table_name='staff_applications')
    op.drop_table('staff_applications')
