"""
Add timezone field to user
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_timezone_to_user'
down_revision = 'add_nutrition_json_to_image'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('users', sa.Column('timezone', sa.String(length=40), nullable=True, server_default='Asia/Jakarta'))

def downgrade():
    op.drop_column('users', 'timezone')
