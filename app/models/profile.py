from app import db
from datetime import datetime
import json

class Profile(db.Model):
    __tablename__ = 'profiles'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    phone_number = db.Column(db.String(20), unique=True, nullable=False)
    description = db.Column(db.Text)
    timezone = db.Column(db.String(50), default='UTC')
    is_active = db.Column(db.Boolean, default=True)
    ai_enabled = db.Column(db.Boolean, default=False)
    business_hours = db.Column(db.Text)  # JSON string
    daily_auto_response_limit = db.Column(db.Integer, default=100)
    
    # SignalWire specific fields
    signalwire_number_sid = db.Column(db.String(50))  # SignalWire phone number SID
    signalwire_webhook_configured = db.Column(db.Boolean, default=False)
    signalwire_last_sync = db.Column(db.DateTime)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', back_populates='profiles')
    messages = db.relationship('Message', back_populates='profile', lazy='dynamic')
    
    def get_business_hours(self):
        if not self.business_hours:
            return {}
        return json.loads(self.business_hours)
    
    def set_business_hours(self, hours_dict):
        self.business_hours = json.dumps(hours_dict)
    
    def is_signalwire_configured(self):
        """Check if this profile is properly configured with SignalWire"""
        return (self.signalwire_number_sid and 
                self.signalwire_webhook_configured and 
                self.phone_number)
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'name': self.name,
            'phone_number': self.phone_number,
            'description': self.description,
            'timezone': self.timezone,
            'is_active': self.is_active,
            'ai_enabled': self.ai_enabled,
            'business_hours': self.get_business_hours(),
            'daily_auto_response_limit': self.daily_auto_response_limit,
            'signalwire_configured': self.is_signalwire_configured(),
            'signalwire_number_sid': self.signalwire_number_sid,
            'signalwire_webhook_configured': self.signalwire_webhook_configured,
            'signalwire_last_sync': self.signalwire_last_sync.isoformat() if self.signalwire_last_sync else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
