"""Separate access to staff approvals from ordinary administrative access.

Revision ID: 0009_staff_manager
Revises: 0008_staff_approval
"""
from alembic import op
import sqlalchemy as sa

revision = '0009_staff_manager'
down_revision = '0008_staff_approval'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column(
        'can_manage_staff', sa.Boolean(), nullable=False, server_default=sa.text('false')
    ))
    # Preserve the powers of existing, manually approved managers only.
    # Newly registered and newly approved staff retain can_manage_staff=false.
    op.execute('UPDATE users SET can_manage_staff = true WHERE is_admin = true')


def downgrade():
    op.drop_column('users', 'can_manage_staff')
