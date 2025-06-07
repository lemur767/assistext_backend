from app.extensions import db
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
    signalwire_sid = db.Column(db.String(50))  # SignalWire phone number SID
    webhook_configured = db.Column(db.Boolean, default=False)
    webhook_url = db.Column(db.String(500))

    
    # Performance tracking
    total_messages_received = db.Column(db.Integer, default=0)
    total_ai_responses_sent = db.Column(db.Integer, default=0)
    avg_response_time = db.Column(db.Float)  # Average AI response time in seconds
    
    # Safety and moderation
    auto_moderation_enabled = db.Column(db.Boolean, default=True)
    strict_safety_mode = db.Column(db.Boolean, default=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', back_populates='profiles')
    messages = db.relationship('Message', back_populates='profile', lazy='dynamic', 
                              order_by='Message.timestamp.desc()')
    text_examples = db.relationship('TextExample', back_populates='profile', lazy='dynamic')
    auto_replies = db.relationship('AutoReply', back_populates='profile', lazy='dynamic')
    out_of_office_replies = db.relationship('OutOfOfficeReply', back_populates='profile', lazy='dynamic')
    ai_settings = db.relationship('AIModelSettings', back_populates='profile', uselist=False)
    profile_clients = db.relationship('ProfileClient', back_populates='profile')
    
    def get_business_hours(self):
        """Parse business hours JSON"""
        if not self.business_hours:
            return {}
        try:
            return json.loads(self.business_hours)
        except:
            return {}
    
    def set_business_hours(self, hours_dict):
        """Set business hours from dict"""
        self.business_hours = json.dumps(hours_dict)
    
    def get_daily_ai_usage(self, date=None):
        """Get AI response count for specific date"""
        if not date:
            date = datetime.utcnow().date()
        
        return self.messages.filter(
            Message.ai_generated == True,
            Message.is_incoming == False,
            db.func.date(Message.timestamp) == date
        ).count()
    
    def get_conversation_stats(self, days=7):
        """Get conversation statistics for the profile"""
        from datetime import timedelta
        since_date = datetime.utcnow() - timedelta(days=days)
        
        return {
            'total_conversations': self.messages.filter(
                Message.timestamp >= since_date
            ).distinct(Message.sender_number).count(),
            
            'total_messages': self.messages.filter(
                Message.timestamp >= since_date
            ).count(),
            
            'ai_responses': self.messages.filter(
                Message.timestamp >= since_date,
                Message.ai_generated == True,
                Message.is_incoming == False
            ).count(),
            
            'flagged_messages': self.messages.filter(
                Message.timestamp >= since_date,
                Message.flagged == True
            ).count()
        }
    
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
            'signalwire_sid': self.signalwire_sid,
            'webhook_configured': self.webhook_configured,
            'webhook_url': self.webhook_url,
            'total_messages_received': self.total_messages_received,
            'total_ai_responses_sent': self.total_ai_responses_sent,
            'avg_response_time': self.avg_response_time,
            'auto_moderation_enabled': self.auto_moderation_enabled,
            'strict_safety_mode': self.strict_safety_mode,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

