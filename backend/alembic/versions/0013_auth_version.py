"""Invalidate old JWT sessions when a staff member changes password.

Revision ID: 0013_auth_version
Revises: 0012_staff_notifications
"""
from alembic import op
import sqlalchemy as sa

revision = '0013_auth_version'
down_revision = '0012_staff_notifications'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column(
        'auth_version', sa.Integer(), nullable=False, server_default=sa.text('0')
    ))
    op.create_check_constraint('ck_users_auth_version_nonnegative', 'users', 'auth_version >= 0')


def downgrade():
    op.drop_constraint('ck_users_auth_version_nonnegative', 'users', type_='check')
    op.drop_column('users', 'auth_version')
