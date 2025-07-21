# migrations/versions/xxx_add_client_id_foreign_key.py
"""Add client_id foreign key to messages table

Revision ID: xxx
Revises: xxx
Create Date: 2025-01-xx xx:xx:xx.xxxxx

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'c0bd1cek643'
down_revision = 'c0a8d1cec642'
branch_labels = None
depends_on = None

def upgrade():
    # Add client_id column
    op.add_column('messages', sa.Column('client_id', sa.Integer(), nullable=True))
    
    # Add foreign key constraint
    op.create_foreign_key(
        'fk_messages_client_id',
        'messages', 'clients',
        ['client_id'], ['id'],
        ondelete='SET NULL'
    )
    
    # Add index for performance
    op.create_index('idx_messages_client_id', 'messages', ['client_id'])

def downgrade():
    op.drop_index('idx_messages_client_id', 'messages')
    op.drop_constraint('fk_messages_client_id', 'messages', type_='foreignkey')
    op.drop_column('messages', 'client_id')
