"""
Add user_id to images table
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_user_id_to_image'
down_revision = 'add61567ae5e'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('images', sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True))

def downgrade():
    op.drop_column('images', 'user_id')
