revision = 'add_recommendation_table'
down_revision = 'add_is_verified_to_users'
"""
Add recommendations table
"""
from alembic import op
import sqlalchemy as sa

def upgrade():
    pass  # Tabel sudah ada, tidak perlu dibuat lagi

def downgrade():
    op.drop_table('recommendations')
