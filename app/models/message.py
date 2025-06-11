from app import db
from datetime import datetime

class Message(db.Model):
    __tablename__ = 'messages'
    
    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(db.Integer, db.ForeignKey('profiles.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_incoming = db.Column(db.Boolean, nullable=False)
    sender_number = db.Column(db.String(20), nullable=False)
    
    # SignalWire specific fields
    signalwire_message_sid = db.Column(db.String(50))  # SignalWire message SID
    signalwire_account_sid = db.Column(db.String(50))  # SignalWire account SID
    signalwire_status = db.Column(db.String(20), default='pending')  # SignalWire delivery status
    signalwire_error_code = db.Column(db.String(10))   # SignalWire error code if any
    signalwire_error_message = db.Column(db.Text)      # SignalWire error message
    
    ai_generated = db.Column(db.Boolean, default=False)
    is_read = db.Column(db.Boolean, default=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    profile = db.relationship('Profile', back_populates='messages')
    
    def to_dict(self):
        return {
            'id': self.id,
            'profile_id': self.profile_id,
            'content': self.content,
            'is_incoming': self.is_incoming,
            'sender_number': self.sender_number,
            'signalwire_message_sid': self.signalwire_message_sid,
            'signalwire_account_sid': self.signalwire_account_sid,
            'signalwire_status': self.signalwire_status,
            'signalwire_error_code': self.signalwire_error_code,
            'ai_generated': self.ai_generated,
            'is_read': self.is_read,
            'timestamp': self.timestamp.isoformat()
        }
    
    @property
    def delivery_status(self):
        """Human-readable delivery status"""
        status_map = {
            'pending': 'Pending',
            'queued': 'Queued',
            'sending': 'Sending',
            'sent': 'Sent',
            'receiving': 'Receiving',
            'received': 'Received',
            'delivered': 'Delivered',
            'undelivered': 'Undelivered',
            'failed': 'Failed'
        }
        return status_map.get(self.signalwire_status, 'Unknown')
    
    @property
    def has_error(self):
        """Check if message has SignalWire error"""
        return bool(self.signalwire_error_code or self.signalwire_error_message)
