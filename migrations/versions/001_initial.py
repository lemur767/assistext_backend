from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Create users table
    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('username', sa.String(length=100), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('password_hash', sa.String(length=255), nullable=False),
    sa.Column('first_name', sa.String(length=100), nullable=True),
    sa.Column('last_name', sa.String(length=100), nullable=True),
    sa.Column('phone_number', sa.String(length=20), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=True),
    sa.Column('is_admin', sa.Boolean(), nullable=True),
    sa.Column('last_login', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('email'),
    sa.UniqueConstraint('username')
    )
    
    # Create profiles table
    op.create_table('profiles',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('phone_number', sa.String(length=20), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('timezone', sa.String(length=50), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=True),
    sa.Column('ai_enabled', sa.Boolean(), nullable=True),
    sa.Column('business_hours', sa.Text(), nullable=True),
    sa.Column('daily_auto_response_limit', sa.Integer(), nullable=True),
    sa.Column('signalwire_sid', sa.String(length=50), nullable=True),
    sa.Column('webhook_configured', sa.Boolean(), nullable=True),
    sa.Column('webhook_url', sa.String(length=500), nullable=True),
    sa.Column('total_messages_received', sa.Integer(), nullable=True),
    sa.Column('total_ai_responses_sent', sa.Integer(), nullable=True),
    sa.Column('avg_response_time', sa.Float(), nullable=True),
    sa.Column('auto_moderation_enabled', sa.Boolean(), nullable=True),
    sa.Column('strict_safety_mode', sa.Boolean(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('phone_number')
    )
    
    # Create clients table
    op.create_table('clients',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('phone_number', sa.String(length=20), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=True),
    sa.Column('email', sa.String(length=255), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('is_regular', sa.Boolean(), nullable=True),
    sa.Column('is_blocked', sa.Boolean(), nullable=True),
    sa.Column('is_flagged', sa.Boolean(), nullable=True),
    sa.Column('risk_level', sa.String(length=20), nullable=True),
    sa.Column('total_messages', sa.Integer(), nullable=True),
    sa.Column('first_contact', sa.DateTime(), nullable=True),
    sa.Column('last_contact', sa.DateTime(), nullable=True),
    sa.Column('last_ai_response', sa.DateTime(), nullable=True),
    sa.Column('city', sa.String(length=100), nullable=True),
    sa.Column('state', sa.String(length=50), nullable=True),
    sa.Column('country', sa.String(length=50), nullable=True),
    sa.Column('timezone', sa.String(length=50), nullable=True),
    sa.Column('device_type', sa.String(length=50), nullable=True),
    sa.Column('preferred_communication_time', sa.String(length=50), nullable=True),
    sa.Column('response_preference', sa.String(length=20), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('phone_number')
    )
    
    # Create messages table
    op.create_table('messages',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('profile_id', sa.Integer(), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('sender_number', sa.String(length=20), nullable=False),
    sa.Column('is_incoming', sa.Boolean(), nullable=False),
    sa.Column('ai_generated', sa.Boolean(), nullable=True),
    sa.Column('timestamp', sa.DateTime(), nullable=False),
    sa.Column('is_read', sa.Boolean(), nullable=True),
    sa.Column('signalwire_sid', sa.String(length=50), nullable=True),
    sa.Column('send_status', sa.String(length=20), nullable=True),
    sa.Column('send_error', sa.Text(), nullable=True),
    sa.Column('status_updated_at', sa.DateTime(), nullable=True),
    sa.Column('ai_model_used', sa.String(length=50), nullable=True),
    sa.Column('ai_processing_time', sa.Float(), nullable=True),
    sa.Column('ai_fallback_used', sa.Boolean(), nullable=True),
    sa.Column('flagged', sa.Boolean(), nullable=True),
    sa.Column('conversation_turn', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['profile_id'], ['profiles.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    
    # Create remaining tables...
    # (Continue with other tables as needed)
    
    # Create indexes for performance
    op.create_index(op.f('ix_messages_profile_id'), 'messages', ['profile_id'], unique=False)
    op.create_index(op.f('ix_messages_sender_number'), 'messages', ['sender_number'], unique=False)
    op.create_index(op.f('ix_messages_timestamp'), 'messages', ['timestamp'], unique=False)
    op.create_index(op.f('ix_messages_is_incoming'), 'messages', ['is_incoming'], unique=False)
    op.create_index(op.f('ix_messages_ai_generated'), 'messages', ['ai_generated'], unique=False)
    op.create_index(op.f('ix_clients_phone_number'), 'clients', ['phone_number'], unique=False)
    op.create_index(op.f('ix_profiles_user_id'), 'profiles', ['user_id'], unique=False)


def downgrade():
    # Drop indexes
    op.drop_index(op.f('ix_profiles_user_id'), table_name='profiles')
    op.drop_index(op.f('ix_clients_phone_number'), table_name='clients')
    op.drop_index(op.f('ix_messages_ai_generated'), table_name='messages')
    op.drop_index(op.f('ix_messages_is_incoming'), table_name='messages')
    op.drop_index(op.f('ix_messages_timestamp'), table_name='messages')
    op.drop_index(op.f('ix_messages_sender_number'), table_name='messages')
    op.drop_index(op.f('ix_messages_profile_id'), table_name='messages')
    
    # Drop tables
    op.drop_table('messages')
    op.drop_table('clients')
    op.drop_table('profiles')
    op.drop_table('users')