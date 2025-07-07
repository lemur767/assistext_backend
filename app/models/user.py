# app/models/user.py - Consolidated User Model
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db
from datetime import datetime
import json


class User(db.Model):
    __tablename__ = 'users'
    
    # Basic Authentication & Identity
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    
    # Personal Information
    first_name = db.Column(db.String(100))
    last_name = db.Column(db.String(100))
    personal_phone = db.Column(db.String(20))  # User's personal phone
    
    # Service Configuration (formerly in Profile)
    business_name = db.Column(db.String(200))  # Business/service name
    business_phone = db.Column(db.String(20), unique=True)  # SMS service phone number
    business_description = db.Column(db.Text)
    timezone = db.Column(db.String(50), default='UTC')
    business_hours = db.Column(db.Text)  # JSON string for business hours
    
    # AI Settings
    ai_enabled = db.Column(db.Boolean, default=True)
    ai_model = db.Column(db.String(50), default='gpt-4')
    ai_temperature = db.Column(db.Float, default=0.7)
    ai_max_tokens = db.Column(db.Integer, default=150)
    ai_personality = db.Column(db.Text)  # Custom AI personality instructions
    
    # Service Settings
    auto_reply_enabled = db.Column(db.Boolean, default=True)
    daily_response_limit = db.Column(db.Integer, default=100)
    response_delay_seconds = db.Column(db.Integer, default=2)  # Delay to seem human
    
    # SignalWire Integration
    signalwire_phone_sid = db.Column(db.String(100))  # SignalWire phone number SID
    signalwire_configured = db.Column(db.Boolean, default=False)
    
    # Usage Tracking
    total_messages_sent = db.Column(db.Integer, default=0)
    total_messages_received = db.Column(db.Integer, default=0)
    monthly_message_count = db.Column(db.Integer, default=0)
    last_message_reset = db.Column(db.Date, default=datetime.utcnow().date())
    
    # Account Status
    is_active = db.Column(db.Boolean, default=True)
    is_admin = db.Column(db.Boolean, default=False)
    is_verified = db.Column(db.Boolean, default=False)
    subscription_status = db.Column(db.String(20), default='free')  # free, active, cancelled, etc.
    
    # Timestamps
    last_login = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships - Direct to user, no profiles
    messages = db.relationship('Message', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    clients = db.relationship('Client', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    
    def set_password(self, password: str) -> None:
        """Set user password hash"""
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password: str) -> bool:
        """Check if provided password matches hash"""
        return check_password_hash(self.password_hash, password)
    
    def get_business_hours(self):
        """Parse business hours JSON"""
        if not self.business_hours:
            return {}
        try:
            return json.loads(self.business_hours)
        except (json.JSONDecodeError, TypeError):
            return {}
    
    def set_business_hours(self, hours_dict):
        """Set business hours as JSON"""
        self.business_hours = json.dumps(hours_dict)
    
    @property
    def full_name(self) -> str:
        """Get user's full name"""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.first_name:
            return self.first_name
        elif self.last_name:
            return self.last_name
        return self.username
    
    @property
    def display_name(self) -> str:
        """Get display name for business"""
        return self.business_name or self.full_name or self.username
    
    def reset_monthly_usage(self):
        """Reset monthly message count"""
        self.monthly_message_count = 0
        self.last_message_reset = datetime.utcnow().date()
        db.session.commit()
    
    def increment_message_count(self, sent: bool = True):
        """Increment message counters"""
        self.monthly_message_count += 1
        if sent:
            self.total_messages_sent += 1
        else:
            self.total_messages_received += 1
        
        # Check if we need to reset monthly count
        if self.last_message_reset != datetime.utcnow().date():
            days_passed = (datetime.utcnow().date() - self.last_message_reset).days
            if days_passed >= 30:  # Reset monthly
                self.reset_monthly_usage()
    
    def can_send_message(self) -> bool:
        """Check if user can send more messages this month"""
        return self.monthly_message_count < self.daily_response_limit
    
    def to_dict(self, include_sensitive: bool = False):
        """Convert user to dictionary"""
        data = {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'full_name': self.full_name,
            'personal_phone': self.personal_phone,
            
            # Business info
            'business_name': self.business_name,
            'business_phone': self.business_phone,
            'business_description': self.business_description,
            'display_name': self.display_name,
            'timezone': self.timezone,
            'business_hours': self.get_business_hours(),
            
            # AI settings
            'ai_enabled': self.ai_enabled,
            'ai_model': self.ai_model,
            'ai_temperature': self.ai_temperature,
            'ai_max_tokens': self.ai_max_tokens,
            'ai_personality': self.ai_personality,
            
            # Service settings
            'auto_reply_enabled': self.auto_reply_enabled,
            'daily_response_limit': self.daily_response_limit,
            'response_delay_seconds': self.response_delay_seconds,
            
            # Status
            'is_active': self.is_active,
            'is_verified': self.is_verified,
            'subscription_status': self.subscription_status,
            'signalwire_configured': self.signalwire_configured,
            
            # Usage stats
            'monthly_message_count': self.monthly_message_count,
            'total_messages_sent': self.total_messages_sent,
            'total_messages_received': self.total_messages_received,
            
            # Timestamps
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
        
        # Include sensitive data only if requested (for admin/self)
        if include_sensitive:
            data.update({
                'is_admin': self.is_admin,
                'signalwire_phone_sid': self.signalwire_phone_sid,
            })
        
        return data
    
    def __repr__(self):
        return f'<User {self.username}>'