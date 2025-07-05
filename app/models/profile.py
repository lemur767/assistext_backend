from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db
from datetime import datetime
import json
from typing import Dict, Any, Optional

class Profile(db.Model):
    __tablename__ = 'profile'
     
    profile_id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    phone_number_sid = db.Column(db.String(34), nullable=True, index=True)
    friendly_name = db.Column(db.String(100), nullable=True)
    # Basic Profile Information (moved from separate profile table)
    first_name = db.Column(db.String(100))
    last_name = db.Column(db.String(100))
    phone_number = db.Column(db.String(20))
    display_name = db.Column(db.String(100))  # How they want to be addressed
    timezone = db.Column(db.String(50), default='UTC')
    
    # SignalWire Configuration
    signalwire_phone_number = db.Column(db.String(20), unique=True, nullable=True)
    signalwire_project_id = db.Column(db.String(100))
    signalwire_auth_token = db.Column(db.String(100))
    signalwire_space_url = db.Column(db.String(200))
    signalwire_webhook_configured = db.Column(db.Boolean, default=False)
    
    # Business Settings
    business_hours = db.Column(db.Text)  # JSON string for business hours
    auto_reply_enabled = db.Column(db.Boolean, default=True)
    out_of_office_enabled = db.Column(db.Boolean, default=False)
    out_of_office_message = db.Column(db.Text)
    daily_message_limit = db.Column(db.Integer, default=100)
    
    # AI Configuration
    ai_enabled = db.Column(db.Boolean, default=True)
    ai_personality = db.Column(db.Text)  # How the AI should behave
    ai_instructions = db.Column(db.Text)  # Specific instructions for the AI
    ai_model = db.Column(db.String(50), default='gpt-4')
    ai_temperature = db.Column(db.Float, default=0.7)
    ai_max_tokens = db.Column(db.Integer, default=150)
    
    # Usage Tracking
    total_messages_sent = db.Column(db.Integer, default=0)
    total_messages_received = db.Column(db.Integer, default=0)
    monthly_message_count = db.Column(db.Integer, default=0)
    last_reset_date = db.Column(db.Date, default=datetime.utcnow().date())
     
    # Account Status
    is_active = db.Column(db.Boolean, default=True)
    is_admin = db.Column(db.Boolean, default=False)
    is_verified = db.Column(db.Boolean, default=False)
    last_login = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
     
    # Relationships (One-to-Many)
    clients = db.relationship('Client', back_populates='user', lazy='dynamic', cascade='all, delete-orphan')
    messages = db.relationship('Message', back_populates='user', lazy='dynamic', cascade='all, delete-orphan')
    text_examples = db.relationship('TextExample', back_populates='user', lazy='dynamic', cascade='all, delete-orphan')
    auto_replies = db.relationship('AutoReply', back_populates='user', lazy='dynamic', cascade='all, delete-orphan')
    activity_logs = db.relationship('ActivityLog', back_populates='user', lazy='dynamic')
    
    def set_password(self, password: str) -> None:
        """Set user password hash"""
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password: str) -> bool:
        """Check if provided password matches hash"""
        return check_password_hash(self.password_hash, password)
     
    @property
    def full_name(self) -> str:
        """Get user's full name"""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.first_name:
            return self.first_name
        elif self.last_name:
            return self.last_name
        else:
            return self.username
     
    
    
    def get_business_hours(self) -> Dict[str, Any]:
        """Get business hours as dictionary"""
        if not self.business_hours:
            return {
                'monday': {'enabled': True, 'start': '09:00', 'end': '17:00'},
                'tuesday': {'enabled': True, 'start': '09:00', 'end': '17:00'},
                'wednesday': {'enabled': True, 'start': '09:00', 'end': '17:00'},
                'thursday': {'enabled': True, 'start': '09:00', 'end': '17:00'},
                'friday': {'enabled': True, 'start': '09:00', 'end': '17:00'},
                'saturday': {'enabled': False, 'start': '09:00', 'end': '17:00'},
                'sunday': {'enabled': False, 'start': '09:00', 'end': '17:00'}
            }
        try:
            return json.loads(self.business_hours)
        except (json.JSONDecodeError, TypeError):
            return {}
    
    def set_business_hours(self, hours_dict: Dict[str, Any]) -> None:
        """Set business hours from dictionary"""
        self.business_hours = json.dumps(hours_dict)
    
    def is_signalwire_configured(self) -> bool:
        """Check if SignalWire is properly configured"""
        return bool(
            self.signalwire_project_id and 
            self.signalwire_auth_token and 
            self.signalwire_space_url and
            self.signalwire_phone_number
        )
     
    def get_ai_settings(self) -> Dict[str, Any]:
        """Get AI configuration as dictionary"""
        return {
            'enabled': self.ai_enabled,
            'personality': self.ai_personality or "You are a helpful and professional assistant.",
            'instructions': self.ai_instructions or "Respond helpfully and professionally to messages.",
            'model': self.ai_model,
            'temperature': self.ai_temperature,
            'max_tokens': self.ai_max_tokens
        }
    
    def update_message_count(self, sent: int = 0, received: int = 0) -> None:
        """Update message counts"""
        self.total_messages_sent += sent
        self.total_messages_received += received
        self.monthly_message_count += (sent + received)
     
    def reset_monthly_count_if_needed(self) -> None:
        """Reset monthly count if it's a new month"""
        today = datetime.utcnow().date()
        if self.last_reset_date.month != today.month or self.last_reset_date.year != today.year:
            self.monthly_message_count = 0
            self.last_reset_date = today
    
    def to_dict(self, include_sensitive: bool = False) -> Dict[str, Any]:
        """Convert user to dictionary"""
        data = {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'full_name': self.full_name,
            'display_name': self.display_name,
            'phone_number': self.phone_number,
            'timezone': self.timezone,
            'signalwire_phone_number': self.signalwire_phone_number,
            'signalwire_configured': self.is_signalwire_configured(),
            'business_hours': self.get_business_hours(),
            'auto_reply_enabled': self.auto_reply_enabled,
            'out_of_office_enabled': self.out_of_office_enabled,
            'out_of_office_message': self.out_of_office_message,
            'daily_message_limit': self.daily_message_limit,
            'ai_settings': self.get_ai_settings(),
            'usage_stats': {
                'total_sent': self.total_messages_sent,
                'total_received': self.total_messages_received,
                'monthly_count': self.monthly_message_count,
                'daily_limit': self.daily_message_limit
            },
            'is_active': self.is_active,
            'is_verified': self.is_verified,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
        
     # Include sensitive data only if requested (for profile settings)
        if include_sensitive:
            data.update({
                'signalwire_project_id': self.signalwire_project_id,
                'signalwire_space_url': self.signalwire_space_url,
                # Note: Never include auth_token in API responses
            })
        
        return data