from app.extensions import db
from datetime import datetime
import json


class Message(db.Model):
    __tablename__ = 'messages'
    
    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(db.Integer, db.ForeignKey('profiles.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    sender_number = db.Column(db.String(20), nullable=False)
    is_incoming = db.Column(db.Boolean, nullable=False)
    ai_generated = db.Column(db.Boolean, default=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    
    # SignalWire specific fields (replacing Twilio)
    signalwire_sid = db.Column(db.String(50))
    send_status = db.Column(db.String(20))  # queued, sending, sent, delivered, failed
    send_error = db.Column(db.Text)
    status_updated_at = db.Column(db.DateTime)
    
    # AI processing metadata
    ai_model_used = db.Column(db.String(50))  # Track which model generated response
    ai_processing_time = db.Column(db.Float)  # Processing time in seconds
    ai_fallback_used = db.Column(db.Boolean, default=False)  # If OpenAI fallback was used
    
    # Analytics and safety
    flagged = db.Column(db.Boolean, default=False)
    conversation_turn = db.Column(db.Integer)  # Position in conversation
    
    # Relationships
    profile = db.relationship('Profile', back_populates='messages')
    flagged_details = db.relationship('FlaggedMessage', back_populates='message', uselist=False)
    
    def to_dict(self):
        return {
            'id': self.id,
            'profile_id': self.profile_id,
            'content': self.content,
            'sender_number': self.sender_number,
            'is_incoming': self.is_incoming,
            'ai_generated': self.ai_generated,
            'timestamp': self.timestamp.isoformat(),
            'is_read': self.is_read,
            'signalwire_sid': self.signalwire_sid,
            'send_status': self.send_status,
            'send_error': self.send_error,
            'ai_model_used': self.ai_model_used,
            'ai_processing_time': self.ai_processing_time,
            'flagged': self.flagged,
            'conversation_turn': self.conversation_turn
        }
    
    def __repr__(self):
        return f'<Message {self.id}: {self.content[:50]}...>'

