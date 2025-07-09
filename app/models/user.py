from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db
from datetime import datetime
import json
from typing import Dict, Any, Optional

# FIXED: Handle existing user_clients table properly
# Check if user_clients table already exists before creating
def create_user_clients_table():
    """Create user_clients table only if it doesn't exist"""
    try:
        # Try to query the table - if it fails, table doesn't exist
        db.session.execute(db.text("SELECT 1 FROM user_clients LIMIT 1"))
        # If we get here, table exists
        return db.Table('user_clients', db.metadata, autoload_with=db.engine)
    except:
        # Table doesn't exist, create it
        return db.Table('user_clients',
            db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
            db.Column('client_id', db.Integer, db.ForeignKey('clients.id'), primary_key=True),
            db.Column('notes', db.Text, default=''),
            db.Column('is_blocked', db.Boolean, default=False),
            db.Column('is_favorite', db.Boolean, default=False),
            db.Column('created_at', db.DateTime, default=datetime.utcnow)
        )

# Create or get the junction table
try:
    user_clients = create_user_clients_table()
except Exception as e:
    # Fallback: define the table structure anyway
    user_clients = db.Table('user_clients',
        db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
        db.Column('client_id', db.Integer, db.ForeignKey('clients.id'), primary_key=True),
        db.Column('notes', db.Text, default=''),
        db.Column('is_blocked', db.Boolean, default=False),
        db.Column('is_favorite', db.Boolean, default=False),
        db.Column('created_at', db.DateTime, default=datetime.utcnow)
    )


class User(db.Model):
    __tablename__ = 'users'
     
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    
    # Basic Profile Information (migrated from profile table)
    first_name = db.Column(db.String(100))
    last_name = db.Column(db.String(100))
    phone_number = db.Column(db.String(20))
    display_name = db.Column(db.String(100))  # How they want to be addressed
    timezone = db.Column(db.String(50), default='UTC')
    
    # SignalWire Configuration (migrated from profile)
    signalwire_phone_number = db.Column(db.String(20), unique=True, nullable=True, index=True)
    signalwire_project_id = db.Column(db.String(100))
    signalwire_auth_token = db.Column(db.String(100))
    signalwire_space_url = db.Column(db.String(200))
    signalwire_webhook_configured = db.Column(db.Boolean, default=False)
    
    # Business Settings (migrated from profile)
    business_hours = db.Column(db.Text)  # JSON string for business hours
    auto_reply_enabled = db.Column(db.Boolean, default=True)
    out_of_office_enabled = db.Column(db.Boolean, default=False)
    out_of_office_message = db.Column(db.Text)
    daily_message_limit = db.Column(db.Integer, default=100)
    
    # AI Configuration (migrated from AI settings table)
    ai_enabled = db.Column(db.Boolean, default=True)
    ai_personality = db.Column(db.Text)  # How the AI should behave
    ai_instructions = db.Column(db.Text)  # Specific instructions for AI
    ai_model = db.Column(db.String(50), default='gpt-3.5-turbo')
    ai_temperature = db.Column(db.Float, default=0.7)
    ai_max_tokens = db.Column(db.Integer, default=150)
    
    # Auto Reply Settings (migrated from auto_reply table)
    auto_reply_keywords = db.Column(db.Text)  # JSON string of keyword->response mappings
    
    # Text Examples (migrated from text_example table)
    text_examples = db.Column(db.Text)  # JSON string of example texts for AI training
    
    # Account status
    is_active = db.Column(db.Boolean, default=True)
    is_verified = db.Column(db.Boolean, default=False)
    is_admin = db.Column(db.Boolean, default=False)
    
    # Usage tracking
    total_messages_sent = db.Column(db.Integer, default=0)
    total_messages_received = db.Column(db.Integer, default=0)
    monthly_message_count = db.Column(db.Integer, default=0)
    last_reset_date = db.Column(db.Date, default=datetime.utcnow().date)
    
    # Timestamps
    last_login = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
 
    message = db.relationship('Message', back_populates='users', lazy='dynamic')
    
    # FIXED: Only define clients relationship if table exists and is properly configured
    try:
        client = db.relationship('Client', secondary=user_clients, back_populates='users', lazy='dynamic')
    except Exception:
        # If there's an issue with the relationship, define it without secondary for now
        pass

    def __init__(self, **kwargs):
        super(User, self).__init__(**kwargs)
        # Set default business hours if not provided
        if not self.business_hours:
            self.set_business_hours({
                'monday': {'start': '09:00', 'end': '17:00', 'enabled': True},
                'tuesday': {'start': '09:00', 'end': '17:00', 'enabled': True},
                'wednesday': {'start': '09:00', 'end': '17:00', 'enabled': True},
                'thursday': {'start': '09:00', 'end': '17:00', 'enabled': True},
                'friday': {'start': '09:00', 'end': '17:00', 'enabled': True},
                'saturday': {'start': '10:00', 'end': '16:00', 'enabled': False},
                'sunday': {'start': '10:00', 'end': '16:00', 'enabled': False}
            })
    
    @property
    def full_name(self) -> str:
        """Get user's full name"""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.first_name:
            return self.first_name
        elif self.display_name:
            return self.display_name
        return self.username
    
    def set_password(self, password: str) -> None:
        """Set user password"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password: str) -> bool:
        """Check user password"""
        return check_password_hash(self.password_hash, password)
    
    def get_business_hours(self) -> Dict[str, Any]:
        """Get parsed business hours"""
        if not self.business_hours:
            return {}
        try:
            return json.loads(self.business_hours)
        except (json.JSONDecodeError, TypeError):
            return {}
    
    def set_business_hours(self, hours_dict: Dict[str, Any]) -> None:
        """Set business hours as JSON string"""
        self.business_hours = json.dumps(hours_dict)
    
    def get_auto_reply_keywords(self) -> Dict[str, str]:
        """Get parsed auto reply keywords"""
        if not self.auto_reply_keywords:
            return {}
        try:
            return json.loads(self.auto_reply_keywords)
        except (json.JSONDecodeError, TypeError):
            return {}
    
    def set_auto_reply_keywords(self, keywords_dict: Dict[str, str]) -> None:
        """Set auto reply keywords as JSON string"""
        self.auto_reply_keywords = json.dumps(keywords_dict)
    
    def get_text_examples(self) -> list:
        """Get parsed text examples"""
        if not self.text_examples:
            return []
        try:
            return json.loads(self.text_examples)
        except (json.JSONDecodeError, TypeError):
            return []
    
    def set_text_examples(self, examples_list: list) -> None:
        """Set text examples as JSON string"""
        self.text_examples = json.dumps(examples_list)
    
    def is_signalwire_configured(self) -> bool:
        """Check if SignalWire is properly configured"""
        return all([
            self.signalwire_phone_number,
            self.signalwire_project_id,
            self.signalwire_auth_token,
            self.signalwire_space_url
        ])
    
    def get_ai_settings(self) -> Dict[str, Any]:
        """Get AI configuration"""
        return {
            'enabled': self.ai_enabled,
            'personality': self.ai_personality or "Respond helpfully and professionally to messages.",
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
            'auto_reply_keywords': self.get_auto_reply_keywords(),
            'out_of_office_enabled': self.out_of_office_enabled,
            'out_of_office_message': self.out_of_office_message,
            'daily_message_limit': self.daily_message_limit,
            'ai_settings': self.get_ai_settings(),
            'text_examples': self.get_text_examples(),
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