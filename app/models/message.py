# app/models/message.py - Updated Message model with SignalWire integration

from app.extensions import db
from datetime import datetime

class Message(db.Model):
    __tablename__ = 'messages'
    
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    is_incoming = db.Column(db.Boolean, nullable=False)
    sender_number = db.Column(db.String(20), nullable=False)
    profile_id = db.Column(db.Integer, db.ForeignKey('profiles.id'), nullable=False)
    ai_generated = db.Column(db.Boolean, default=False)
    is_read = db.Column(db.Boolean, default=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    # SignalWire integration fields
    signalwire_sid = db.Column(db.String(50))  # SignalWire message SID
    send_status = db.Column(db.String(20))     # queued, sending, sent, failed, delivered
    error_code = db.Column(db.String(10))      # SignalWire error code if failed
    error_message = db.Column(db.String(255))  # Error description
    
    # Legacy Twilio field (for migration compatibility)
    twilio_sid = db.Column(db.String(50))
    
    # AI response metadata
    ai_model_used = db.Column(db.String(50))   # Which AI model generated the response
    ai_response_time = db.Column(db.Float)     # Time taken to generate AI response
    ai_confidence = db.Column(db.Float)        # AI confidence score (if available)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    profile = db.relationship('Profile', back_populates='messages')
    
    def to_dict(self):
        return {
            'id': self.id,
            'content': self.content,
            'is_incoming': self.is_incoming,
            'sender_number': self.sender_number,
            'profile_id': self.profile_id,
            'ai_generated': self.ai_generated,
            'is_read': self.is_read,
            'timestamp': self.timestamp.isoformat(),
            'signalwire_sid': self.signalwire_sid,
            'send_status': self.send_status,
            'error_code': self.error_code,
            'ai_model_used': self.ai_model_used,
            'ai_response_time': self.ai_response_time,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }