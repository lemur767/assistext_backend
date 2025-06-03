from app.extensions import db
from datetime import datetime
import json

class Profile(db.Model):
    __tablename__ = 'profiles'
    __table_args__ = {'extend_existing': True}
    
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
    twilio_sid = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', back_populates='profiles')
    messages = db.relationship('Message', back_populates='profile', lazy='dynamic')
    
    # Define the clients relationship correctly
    profile_clients = db.relationship('ProfileClient', back_populates='profile')
    clients = db.relationship('Client', secondary='profile_clients', viewonly=True)

  
    
    # Other relationships
    text_examples = db.relationship('TextExample', back_populates='profile', lazy='dynamic')
    auto_replies = db.relationship('AutoReply', back_populates='profile', lazy='dynamic')
    out_of_office_replies = db.relationship('OutOfOfficeReply', back_populates='profile', lazy='dynamic')
    ai_settings = db.relationship('AIModelSettings', back_populates='profile', uselist=False)
    
    def get_business_hours(self):
        if not self.business_hours:
            return {}
        return json.loads(self.business_hours)
    
    def set_business_hours(self, hours_dict):
        self.business_hours = json.dumps(hours_dict)
    
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
            'twilio_sid': self.twilio_sid,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }