from app.extensions import db
from datetime import datetime
import json

class Message(db.Model):
    __tablename__ = 'messages'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(db.Integer, db.ForeignKey('profiles.id', ondelete='CASCADE'), nullable=False)
    sender_number = db.Column(db.String(20), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_incoming = db.Column(db.Boolean, nullable=False)  # True if from client, False if from profile
    ai_generated = db.Column(db.Boolean, default=False)
    is_read = db.Column(db.Boolean, default=False)
    twilio_sid = db.Column(db.String(50))
    send_status = db.Column(db.String(20))  # 'sent', 'delivered', 'failed'
    send_error = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    profile = db.relationship('Profile', back_populates='messages')
    flagged_message = db.relationship(
        'FlaggedMessage',
        foreign_keys='FlaggedMessage.message_id',
        uselist=False,
        backref=db.backref('message', lazy='joined')
    )
    
    def is_flagged(self):
        """Check if this message has been flagged"""
        return self.flagged_message is not None
    
    def to_dict(self):
        return {
            'id': self.id,
            'content': self.content,
            'is_incoming': self.is_incoming,
            'sender_number': self.sender_number,
            'profile_id': self.profile_id,
            'ai_generated': self.ai_generated,
            'is_read': self.is_read,
            'twilio_sid': self.twilio_sid,
            'send_status': self.send_status,
            'send_error': self.send_error,
            'timestamp': self.timestamp.isoformat(),
            'created_at': self.created_at.isoformat(),
            'is_flagged': self.is_flagged()
        }