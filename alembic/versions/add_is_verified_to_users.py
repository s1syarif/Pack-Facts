"""
Add is_verified field to users table

Revision ID: add_is_verified_to_users
Revises: add_timezone_to_user
Create Date: 2025-07-222
"""
from alembic import op
import sqlalchemy as sa

revision = 'add_is_verified_to_users'
down_revision = 'add_timezone_to_user'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('is_verified', sa.Boolean(), nullable=False, server_default=sa.text('0')))
    op.add_column('users', sa.Column('is_verified', sa.Boolean(), nullable=False, server_default='0'))

def downgrade():
    op.drop_column('users', 'is_verified')
