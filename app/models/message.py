from app.extensions import db
from datetime import datetime
from typing import Dict, Any, Optional

class Message(db.Model):
    __tablename__ = 'messages'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)
    
    # Message Content
    content = db.Column(db.Text, nullable=False)
    direction = db.Column(db.String(20), nullable=False)  # 'incoming' or 'outgoing'
    
    # SignalWire/SMS Details
    signalwire_sid = db.Column(db.String(100), unique=True)  # SignalWire message SID
    from_number = db.Column(db.String(20), nullable=False)
    to_number = db.Column(db.String(20), nullable=False)
    
    # AI Processing
    was_ai_generated = db.Column(db.Boolean, default=False)
    ai_model_used = db.Column(db.String(50))
    ai_processing_time = db.Column(db.Float)  # Time in seconds
    ai_confidence = db.Column(db.Float)  # 0.0 to 1.0
    
    # Message Status
    status = db.Column(db.String(20), default='delivered')  # delivered, failed, pending
    error_message = db.Column(db.Text)  # If delivery failed
    
    # Metadata
    read_at = db.Column(db.DateTime)  # When user read the message
    replied_at = db.Column(db.DateTime)  # When user replied (if applicable)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', back_populates='messages')
    client = db.relationship('Client', back_populates='messages')
    
    def mark_as_read(self) -> None:
        """Mark message as read"""
        if not self.read_at:
            self.read_at = datetime.utcnow()
    
    def is_from_client(self) -> bool:
        """Check if message is from client (incoming)"""
        return self.direction == 'incoming'
    
    def is_from_user(self) -> bool:
        """Check if message is from user (outgoing)"""
        return self.direction == 'outgoing'
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'client_id': self.client_id,
            'content': self.content,
            'direction': self.direction,
            'signalwire_sid': self.signalwire_sid,
            'from_number': self.from_number,
            'to_number': self.to_number,
            'was_ai_generated': self.was_ai_generated,
            'ai_model_used': self.ai_model_used,
            'ai_processing_time': self.ai_processing_time,
            'ai_confidence': self.ai_confidence,
            'status': self.status,
            'error_message': self.error_message,
            'read_at': self.read_at.isoformat() if self.read_at else None,
            'replied_at': self.replied_at.isoformat() if self.replied_at else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
