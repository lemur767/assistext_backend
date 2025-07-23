from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from app.extensions import db

class Message(db.Model):
    """Message model for SMS conversations"""
    __tablename__ = 'messages'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True) 
    # Message details
    from_number = db.Column(db.String(20), nullable=False, index=True)
    to_number = db.Column(db.String(20), nullable=False, index=True)
    body = db.Column(db.Text, nullable=False)
    
    # Message metadata
    direction = db.Column(db.String(10), nullable=False)  # 'inbound', 'outbound'
    status = db.Column(db.String(20), default='pending')  # 'pending', 'sent', 'delivered', 'failed', 'received'
    message_type = db.Column(db.String(10), default='sms')  # 'sms', 'mms'
    
    # External references
    external_id = db.Column(db.String(100), unique=True, index=True)  # SignalWire message SID
    thread_id = db.Column(db.String(100), index=True)  # Conversation thread
    
    # AI processing
    ai_processed = db.Column(db.Boolean, default=False)
    ai_response_generated = db.Column(db.Boolean, default=False)
    ai_confidence_score = db.Column(db.Float)
    ai_processing_time = db.Column(db.Float)  # Time in seconds
    
    # Error handling
    error_message = db.Column(db.Text)
    retry_count = db.Column(db.Integer, default=0)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    sent_at = db.Column(db.DateTime)
    received_at = db.Column(db.DateTime)
    delivered_at = db.Column(db.DateTime)
    failed_at = db.Column(db.DateTime)
    
    # Relationships
    user = db.relationship('User', back_populates='messages')

  
    client = db.relationship('Client', back_populates='messages')


    def __init__(self, **kwargs):
        super(Message, self).__init__(**kwargs)
        
        # Generate thread ID for conversation grouping
        if not self.thread_id:
            self.thread_id = self.generate_thread_id()
    
    def generate_thread_id(self):
        """Generate thread ID for conversation grouping"""
        import hashlib
        
        # Create thread ID from normalized phone numbers
        numbers = sorted([self.from_number, self.to_number])
        thread_string = f"{numbers[0]}:{numbers[1]}:{self.user_id}"
        
        return hashlib.md5(thread_string.encode()).hexdigest()[:16]
    
    @property
    def is_from_client(self):
        """Check if message is from client (inbound)"""
        return self.direction == 'inbound'
    
    @property
    def client_number(self):
        """Get client phone number"""
        return self.from_number if self.is_from_client else self.to_number
    
    @property
    def conversation_partner(self):
        """Get the other party in conversation"""
        user = self.user
        if user and user.signalwire_phone_number:
            return self.from_number if self.from_number != user.signalwire_phone_number else self.to_number
        return self.from_number if self.direction == 'inbound' else self.to_number
    
    def to_dict(self, include_ai_data=False):
        """Convert message to dictionary"""
        data = {
            'id': self.id,
            'user_id': self.user_id,
            'from_number': self.from_number,
            'to_number': self.to_number,
            'body': self.body,
            'direction': self.direction,
            'status': self.status,
            'message_type': self.message_type,
            'thread_id': self.thread_id,
            'is_from_client': self.is_from_client,
            'conversation_partner': self.conversation_partner,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'received_at': self.received_at.isoformat() if self.received_at else None,
            'delivered_at': self.delivered_at.isoformat() if self.delivered_at else None
        }
        
        if include_ai_data:
            data.update({
                'ai_processed': self.ai_processed,
                'ai_response_generated': self.ai_response_generated,
                'ai_confidence_score': self.ai_confidence_score,
                'ai_processing_time': self.ai_processing_time
            })
        
        return data
    
    @staticmethod
    def get_conversation_history(user_id, client_number, limit=50):
        """Get conversation history between user and client"""
        return Message.query.filter(
            Message.user_id == user_id,
            db.or_(
                db.and_(Message.from_number == client_number, Message.direction == 'inbound'),
                db.and_(Message.to_number == client_number, Message.direction == 'outbound')
            )
        ).order_by(Message.created_at.desc()).limit(limit).all()
    
    def __repr__(self):
        return f'<Message {self.id}: {self.direction} {self.from_number}->{self.to_number}>'
