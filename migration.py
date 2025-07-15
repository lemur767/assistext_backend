# database/migrations/add_signalwire_integration.py
"""Add SignalWire integration fields

Revision ID: add_signalwire_integration
Revises: previous_migration
Create Date: 2025-01-14

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = 'add_signalwire_integration'
down_revision = 'previous_migration'
branch_labels = None
depends_on = None

def upgrade():
    # Add SignalWire fields to users table
    op.add_column('users', sa.Column('signalwire_subproject_id', sa.String(100), nullable=True))
    op.add_column('users', sa.Column('signalwire_subproject_token', sa.Text, nullable=True))
    op.add_column('users', sa.Column('signalwire_phone_number', sa.String(20), nullable=True))
    op.add_column('users', sa.Column('signalwire_phone_number_sid', sa.String(100), nullable=True))
    op.add_column('users', sa.Column('signalwire_setup_completed', sa.Boolean, default=False))
    op.add_column('users', sa.Column('trial_phone_expires_at', sa.DateTime, nullable=True))
    
    # Create indexes for performance
    op.create_index('idx_users_signalwire_subproject', 'users', ['signalwire_subproject_id'])
    op.create_index('idx_users_phone_number', 'users', ['signalwire_phone_number'])
    
    # Add trial status to subscriptions if not exists
    op.execute("ALTER TYPE subscription_status ADD VALUE IF NOT EXISTS 'trialing'")

def downgrade():
    op.drop_index('idx_users_phone_number', 'users')
    op.drop_index('idx_users_signalwire_subproject', 'users')
    op.drop_column('users', 'trial_phone_expires_at')
    op.drop_column('users', 'signalwire_setup_completed')
    op.drop_column('users', 'signalwire_phone_number_sid')
    op.drop_column('users', 'signalwire_phone_number')
    op.drop_column('users', 'signalwire_subproject_token')
    op.drop_column('users', 'signalwire_subproject_id')
