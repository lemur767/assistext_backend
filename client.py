from alembic import op
import sqlalchemy as sa

def upgrade():
    # Add client_id column
    op.add_column('messages', 
        sa.Column('client_id', sa.Integer(), nullable=True)
    )
    
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
Step 2: Update Message Model
Modify your app/models/message.py to include the client relationship:
pythonclass Message(db.Model):
    """Message model for SMS conversations"""
    __tablename__ = 'messages'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # ✅ ADD THIS: Foreign key to client
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)
    
    # Message details
    from_number = db.Column(db.String(20), nullable=False, index=True)
    to_number = db.Column(db.String(20), nullable=False, index=True)
    body = db.Column(db.Text, nullable=False)
    
    # ... rest of your existing fields ...
    
    # Relationships
    user = db.relationship('User', back_populates='messages')
    
    # ✅ ADD THIS: Relationship to client
    client = db.relationship('Client', back_populates='messages')
