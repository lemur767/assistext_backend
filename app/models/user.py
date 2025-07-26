# app/models/user.py - UPDATED with SignalWire integration
from app.extensions import db
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import uuid

class User(db.Model):
    __tablename__ = 'users'
    
    # Core Identity
    id = db.Column(db.String(50), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    
    # Business Information (consolidated from Profile)
    company_name = db.Column(db.String(255))
    phone_number = db.Column(db.String(20))
    business_description = db.Column(db.Text)
    business_hours_start = db.Column(db.Time)
    business_hours_end = db.Column(db.Time)
    timezone = db.Column(db.String(50), default='America/Toronto')
    
    # SignalWire Integration (ADDED)
    signalwire_subproject_id = db.Column(db.String(100))
    signalwire_subproject_token = db.Column(db.Text)
    signalwire_phone_number = db.Column(db.String(20))
    signalwire_phone_number_sid = db.Column(db.String(100))
    signalwire_setup_completed = db.Column(db.Boolean, default=False)
    
    # AI Configuration (ADDED)
    ai_enabled = db.Column(db.Boolean, default=True)
    ai_model = db.Column(db.String(50), default='dolphin-mistral:7b')
    ai_temperature = db.Column(db.Numeric(3,2), default=0.7)
    ai_max_tokens = db.Column(db.Integer, default=150)
    ai_personality = db.Column(db.Text)
    auto_reply_enabled = db.Column(db.Boolean, default=True)
    auto_reply_delay = db.Column(db.Integer, default=30)
    confidence_threshold = db.Column(db.Numeric(3,2), default=0.8)
    fallback_message = db.Column(db.Text)
    
    # Trial & Subscription
    is_trial_eligible = db.Column(db.Boolean, default=True)
    trial_status = db.Column(db.String(20))  # pending_payment, active, expired, converted
    trial_ends_at = db.Column(db.DateTime)
    trial_warning_sent = db.Column(db.Boolean, default=False)
    subscription_tier = db.Column(db.String(20), default='basic')
    
    # Status & Metadata
    is_active = db.Column(db.Boolean, default=True)
    email_verified = db.Column(db.Boolean, default=False)
    last_login = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    clients = db.relationship('Client', back_populates='user', lazy='dynamic')
    messages = db.relationship('Message', back_populates='user', lazy='dynamic')
    message_templates = db.relationship('MessageTemplate', back_populates='user', lazy='dynamic')
    subscriptions = db.relationship('Subscription', back_populates='user', lazy='dynamic')
    payments = db.relationship('Payment', back_populates='user', lazy='dynamic')
    
    def __init__(self, **kwargs):
        super(User, self).__init__(**kwargs)
        if not self.id:
            self.id = str(uuid.uuid4())
    
    def set_password(self, password):
        """Set password hash"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Check password against hash"""
        return check_password_hash(self.password_hash, password)
    
    @property
    def is_trial_user(self):
        """Check if user is on trial"""
        return self.trial_status == 'active' and self.trial_ends_at and self.trial_ends_at > datetime.utcnow()
    
    @property
    def trial_days_remaining(self):
        """Get remaining trial days"""
        if self.trial_ends_at and self.trial_status == 'active':
            delta = self.trial_ends_at - datetime.utcnow()
            return max(0, delta.days)
        return 0
    
    def setup_signalwire_integration(self, subproject_id, subproject_token, phone_number, phone_sid):
        """Setup SignalWire integration"""
        self.signalwire_subproject_id = subproject_id
        self.signalwire_subproject_token = subproject_token
        self.signalwire_phone_number = phone_number
        self.signalwire_phone_number_sid = phone_sid
        self.signalwire_setup_completed = True
        self.updated_at = datetime.utcnow()
    
    def to_dict(self, include_sensitive=False):
        """Convert to dictionary"""
        data = {
            'id': self.id,
            'email': self.email,
            'name': self.name,
            'company_name': self.company_name,
            'phone_number': self.phone_number,
            'business_description': self.business_description,
            'signalwire_phone_number': self.signalwire_phone_number,
            'signalwire_setup_completed': self.signalwire_setup_completed,
            'ai_enabled': self.ai_enabled,
            'ai_model': self.ai_model,
            'subscription_tier': self.subscription_tier,
            'trial_status': self.trial_status,
            'trial_days_remaining': self.trial_days_remaining,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
        
        if include_sensitive:
            data.update({
                'signalwire_subproject_id': self.signalwire_subproject_id,
                'ai_personality': self.ai_personality
            })
        
        return data