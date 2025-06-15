"""
Add recommendations table
"""
from alembic import op
import sqlalchemy as sa

def upgrade():
    op.create_table(
        'recommendations',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('rekomendasi_json', sa.Text(), nullable=False)
    )

def downgrade():
    op.drop_table('recommendations')
