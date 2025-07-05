from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db
from datetime import datetime, date
import json
from typing import Dict, Any, Optional

class User(db.Model):
    __tablename__ = 'users'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    
    # Basic Profile Information
    first_name = db.Column(db.String(100))
    last_name = db.Column(db.String(100))
    display_name = db.Column(db.String(100))
    phone_number = db.Column(db.String(20))
    timezone = db.Column(db.String(50), default='UTC')
    
    # SignalWire Configuration
    signalwire_phone_number = db.Column(db.String(20), unique=True, nullable=True)
    signalwire_project_id = db.Column(db.String(100))
    signalwire_auth_token = db.Column(db.String(100))
    signalwire_space_url = db.Column(db.String(200))
    signalwire_webhook_configured = db.Column(db.Boolean, default=False)
    
    # Business Settings
    business_hours = db.Column(db.Text)
    auto_reply_enabled = db.Column(db.Boolean, default=True)
    out_of_office_enabled = db.Column(db.Boolean, default=False)
    out_of_office_message = db.Column(db.Text)
    daily_message_limit = db.Column(db.Integer, default=100)
    
    # AI Configuration
    ai_enabled = db.Column(db.Boolean, default=True)
    ai_personality = db.Column(db.Text)
    ai_instructions = db.Column(db.Text)
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
    
    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)
    
    @property
    def full_name(self) -> str:
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.first_name:
            return self.first_name
        elif self.last_name:
            return self.last_name
        else:
            return self.username
    
    @property
    def profile_name(self) -> str:
        return self.display_name or self.full_name
    
    def get_business_hours(self) -> Dict[str, Any]:
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
        self.business_hours = json.dumps(hours_dict)
    
    def is_signalwire_configured(self) -> bool:
        return bool(
            self.signalwire_project_id and 
            self.signalwire_auth_token and 
            self.signalwire_space_url and
            self.signalwire_phone_number
        )
    
    def get_ai_settings(self) -> Dict[str, Any]:
        return {
            'enabled': self.ai_enabled,
            'personality': self.ai_personality or "You are a helpful and professional assistant.",
            'instructions': self.ai_instructions or "Respond helpfully and professionally to messages.",
            'model': self.ai_model,
            'temperature': self.ai_temperature,
            'max_tokens': self.ai_max_tokens
        }
    
    def update_message_count(self, sent: int = 0, received: int = 0) -> None:
        self.total_messages_sent += sent
        self.total_messages_received += received
        self.monthly_message_count += (sent + received)
    
    def reset_monthly_count_if_needed(self) -> None:
        today = datetime.utcnow().date()
        if self.last_reset_date.month != today.month or self.last_reset_date.year != today.year:
            self.monthly_message_count = 0
            self.last_reset_date = today
    
    def to_dict(self, include_sensitive: bool = False) -> Dict[str, Any]:
        data = {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'full_name': self.full_name,
            'display_name': self.display_name,
            'profile_name': self.profile_name,
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
        
        if include_sensitive:
            data.update({
                'signalwire_project_id': self.signalwire_project_id,
                'signalwire_space_url': self.signalwire_space_url,
            })
        
        return data
