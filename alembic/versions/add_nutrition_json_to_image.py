"""
Add nutrition_json to images table

Revision ID: add_nutrition_json_to_image
Revises: add_user_id_to_image
Create Date: 2025-05-31 18:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'add_nutrition_json_to_image'
down_revision = 'add_user_id_to_image'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('images', sa.Column('nutrition_json', sa.Text(), nullable=True))

def downgrade():
    op.drop_column('images', 'nutrition_json')
