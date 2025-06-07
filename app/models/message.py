# app/models/message.py
from app.extensions import db
from datetime import datetime


class Message(db.Model):
    __tablename__ = 'messages'
    
    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(db.Integer, db.ForeignKey('profiles.id'), nullable=False, index=True)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), index=True)
    sender_number = db.Column(db.String(20), nullable=False, index=True)
    content = db.Column(db.Text, nullable=False)
    is_incoming = db.Column(db.Boolean, nullable=False, index=True)
    ai_generated = db.Column(db.Boolean, default=False)
    is_read = db.Column(db.Boolean, default=False)
    send_status = db.Column(db.String(20), default='pending')
    send_error = db.Column(db.Text)
    twilio_sid = db.Column(db.String(50))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    # FIXED: Using message_metadata instead of metadata
    message_metadata = db.Column(db.Text)  # JSON string for additional message data
    
    # Relationships
    profile = db.relationship('Profile', back_populates='messages')
    client = db.relationship('Client', back_populates='messages')
    flagged_message = db.relationship('FlaggedMessage', back_populates='message', uselist=False)
    
    def get_message_metadata(self):
        """Get message metadata as dictionary"""
        if not self.message_metadata:
            return {}
        try:
            import json
            return json.loads(self.message_metadata)
        except (json.JSONDecodeError, TypeError):
            return {}
    
    def set_message_metadata(self, metadata_dict):
        """Set message metadata from dictionary"""
        if metadata_dict:
            import json
            self.message_metadata = json.dumps(metadata_dict)
        else:
            self.message_metadata = None
    
    def to_dict(self):
        return {
            'id': self.id,
            'profile_id': self.profile_id,
            'client_id': self.client_id,
            'sender_number': self.sender_number,
            'content': self.content,
            'is_incoming': self.is_incoming,
            'ai_generated': self.ai_generated,
            'is_read': self.is_read,
            'send_status': self.send_status,
            'send_error': self.send_error,
            'twilio_sid': self.twilio_sid,
            'timestamp': self.timestamp.isoformat(),
            'message_metadata': self.get_message_metadata()
        }
