from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db


class User(db.Model):
    """Core user model - clean and focused"""
    __tablename__ = 'users'
    
    # Primary Key
    id = db.Column(db.Integer, primary_key=True)
    
    # Authentication
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    
    # Personal Information
    first_name = db.Column(db.String(50))
    last_name = db.Column(db.String(50))
    display_name = db.Column(db.String(100))
    personal_phone = db.Column(db.String(20))
    timezone = db.Column(db.String(50), default='UTC')
    
    # Account Status
    is_active = db.Column(db.Boolean, default=True)
    is_admin = db.Column(db.Boolean, default=False)
    email_verified = db.Column(db.Boolean, default=False)
    email_verification_token = db.Column(db.String(100))
    
    # SignalWire Integration
    signalwire_phone_number = db.Column(db.String(20))
    signalwire_configured = db.Column(db.Boolean, default=False)
    signalwire_project_id = db.Column(db.String(100))
    signalwire_space_url = db.Column(db.String(255))
    
    # AI Settings
    ai_enabled = db.Column(db.Boolean, default=True)
    ai_personality = db.Column(db.String(50), default='professional')  # professional, friendly, casual, custom
    ai_response_style = db.Column(db.String(50), default='professional')  # professional, casual, custom
    ai_language = db.Column(db.String(10), default='english')
    use_emojis = db.Column(db.Boolean, default=False)
    casual_language = db.Column(db.Boolean, default=False)
    custom_ai_instructions = db.Column(db.Text)
    
    # Auto Reply Settings
    auto_reply_enabled = db.Column(db.Boolean, default=True)
    custom_greeting = db.Column(db.Text)
    out_of_office_enabled = db.Column(db.Boolean, default=False)
    out_of_office_message = db.Column(db.Text)
    out_of_office_start = db.Column(db.DateTime)
    out_of_office_end = db.Column(db.DateTime)
    
    # Business Hours
    business_hours_enabled = db.Column(db.Boolean, default=False)
    business_hours_start = db.Column(db.String(5))  # HH:MM format
    business_hours_end = db.Column(db.String(5))    # HH:MM format
    business_days = db.Column(db.String(20), default='Monday-Friday')
    after_hours_message = db.Column(db.Text)
    
    # Security Settings
    enable_flagged_word_detection = db.Column(db.Boolean, default=True)
    custom_flagged_words = db.Column(db.Text)  # Comma-separated list
    auto_block_suspicious = db.Column(db.Boolean, default=False)
    require_manual_review = db.Column(db.Boolean, default=False)
    
    # Session Management
    current_session_id = db.Column(db.String(100))
    session_expires_at = db.Column(db.DateTime)
    
    # Password Reset
    password_reset_token = db.Column(db.String(100))
    password_reset_expires = db.Column(db.DateTime)
    
    # External Service IDs (for reference only)
    stripe_customer_id = db.Column(db.String(100))  # For billing service reference
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    last_activity = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Metadata
    user_metadata = db.Column(db.JSON)
    preferences = db.Column(db.JSON)  # UI preferences, notifications, etc.
    
    # =============================================================================
    # RELATIONSHIPS - ORGANIZED BY DOMAIN
    # =============================================================================
    
    # Billing Domain Relationships (from billing.py models)
    subscriptions = db.relationship('Subscription', back_populates='user', lazy='dynamic')
    invoices = db.relationship('Invoice', back_populates='user', lazy='dynamic')
    payment_methods = db.relationship('PaymentMethod', back_populates='user', lazy='dynamic')
    payments = db.relationship('Payment', back_populates='user', lazy='dynamic')
    usage_records = db.relationship('UsageRecord', back_populates='user', lazy='dynamic')
    
    # Messaging Domain Relationships (from messaging.py models)
    clients = db.relationship('Client', back_populates='user', lazy='dynamic')
    messages = db.relationship('Message', back_populates='user', lazy='dynamic')
    message_templates = db.relationship('MessageTemplate', back_populates='user', lazy='dynamic')
    activity_logs = db.relationship('ActivityLog', back_populates='user', lazy='dynamic')
    notification_logs = db.relationship('NotificationLog', back_populates='user', lazy='dynamic')
    
    # =============================================================================
    # PASSWORD MANAGEMENT
    # =============================================================================
    
    def set_password(self, password: str) -> None:
        """Set password hash"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password: str) -> bool:
        """Check password against hash"""
        return check_password_hash(self.password_hash, password)
    
    def generate_password_reset_token(self) -> str:
        """Generate password reset token"""
        import secrets
        token = secrets.token_urlsafe(32)
        self.password_reset_token = token
        self.password_reset_expires = datetime.utcnow() + timedelta(hours=1)
        return token
    
    def verify_password_reset_token(self, token: str) -> bool:
        """Verify password reset token"""
        if not self.password_reset_token or not self.password_reset_expires:
            return False
        
        if datetime.utcnow() > self.password_reset_expires:
            return False
        
        return self.password_reset_token == token
    
    def clear_password_reset_token(self) -> None:
        """Clear password reset token"""
        self.password_reset_token = None
        self.password_reset_expires = None
    
    # =============================================================================
    # EMAIL VERIFICATION
    # =============================================================================
    
    def generate_email_verification_token(self) -> str:
        """Generate email verification token"""
        import secrets
        token = secrets.token_urlsafe(32)
        self.email_verification_token = token
        return token
    
    def verify_email_token(self, token: str) -> bool:
        """Verify email verification token"""
        if self.email_verification_token == token:
            self.email_verified = True
            self.email_verification_token = None
            return True
        return False
    
    # =============================================================================
    # BUSINESS LOGIC PROPERTIES
    # =============================================================================
    
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
    
    @property
    def display_name_or_username(self) -> str:
        """Get display name or fallback to username"""
        return self.display_name or self.full_name or self.username
    
    @property
    def is_signalwire_configured(self) -> bool:
        """Check if SignalWire is properly configured"""
        return (self.signalwire_configured and 
                self.signalwire_phone_number is not None)
    
    @property
    def is_in_business_hours(self) -> bool:
        """Check if current time is within business hours"""
        if not self.business_hours_enabled:
            return True
        
        from datetime import time
        import pytz
        
        try:
            user_tz = pytz.timezone(self.timezone)
            current_time = datetime.now(user_tz).time()
            
            start_time = time.fromisoformat(self.business_hours_start)
            end_time = time.fromisoformat(self.business_hours_end)
            
            return start_time <= current_time <= end_time
        except:
            return True  # Default to always available if time parsing fails
    
    @property
    def is_out_of_office(self) -> bool:
        """Check if user is currently out of office"""
        if not self.out_of_office_enabled:
            return False
        
        now = datetime.utcnow()
        return (self.out_of_office_start and 
                self.out_of_office_end and
                self.out_of_office_start <= now <= self.out_of_office_end)
    
    @property
    def flagged_words_list(self) -> list:
        """Get list of flagged words"""
        if not self.custom_flagged_words:
            return []
        return [word.strip().lower() for word in self.custom_flagged_words.split(',') if word.strip()]
    
    # =============================================================================
    # ACTIVITY TRACKING
    # =============================================================================
    
    def update_last_activity(self) -> None:
        """Update last activity timestamp"""
        self.last_activity = datetime.utcnow()
    
    def update_last_login(self) -> None:
        """Update last login timestamp"""
        self.last_login = datetime.utcnow()
        self.update_last_activity()
    
    # =============================================================================
    # SERIALIZATION
    # =============================================================================
    
    def to_dict(self, include_settings: bool = False, include_stats: bool = False) -> dict:
        """Convert user to dictionary for API responses"""
        data = {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'display_name': self.display_name,
            'full_name': self.full_name,
            'personal_phone': self.personal_phone,
            'timezone': self.timezone,
            'is_active': self.is_active,
            'is_admin': self.is_admin,
            'email_verified': self.email_verified,
            'signalwire_configured': self.signalwire_configured,
            'signalwire_phone_number': self.signalwire_phone_number,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None
        }
        
        if include_settings:
            data.update({
                'ai_enabled': self.ai_enabled,
                'ai_personality': self.ai_personality,
                'ai_response_style': self.ai_response_style,
                'ai_language': self.ai_language,
                'use_emojis': self.use_emojis,
                'casual_language': self.casual_language,
                'custom_ai_instructions': self.custom_ai_instructions,
                'auto_reply_enabled': self.auto_reply_enabled,
                'custom_greeting': self.custom_greeting,
                'out_of_office_enabled': self.out_of_office_enabled,
                'out_of_office_message': self.out_of_office_message,
                'business_hours_enabled': self.business_hours_enabled,
                'business_hours_start': self.business_hours_start,
                'business_hours_end': self.business_hours_end,
                'business_days': self.business_days,
                'after_hours_message': self.after_hours_message,
                'is_in_business_hours': self.is_in_business_hours,
                'is_out_of_office': self.is_out_of_office
            })
        
        if include_stats:
            data.update({
                'total_clients': self.clients.count(),
                'total_messages': self.messages.count(),
                'total_templates': self.message_templates.count(),
                'last_activity': self.last_activity.isoformat() if self.last_activity else None
            })
        
        return data
    
    def to_public_dict(self) -> dict:
        """Convert user to public dictionary (safe for external APIs)"""
        return {
            'id': self.id,
            'username': self.username,
            'display_name': self.display_name_or_username,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    # =============================================================================
    # CLASS METHODS
    # =============================================================================
    
    @classmethod
    def find_by_email(cls, email: str):
        """Find user by email"""
        return cls.query.filter_by(email=email.lower()).first()
    
    @classmethod
    def find_by_username(cls, username: str):
        """Find user by username"""
        return cls.query.filter_by(username=username.lower()).first()
    
    @classmethod
    def find_by_signalwire_number(cls, phone_number: str):
        """Find user by SignalWire phone number"""
        return cls.query.filter_by(signalwire_phone_number=phone_number).first()
    
    @classmethod
    def create_user(cls, username: str, email: str, password: str, **kwargs):
        """Create new user with validation"""
        # Basic validation
        if cls.find_by_email(email):
            raise ValueError("Email already exists")
        if cls.find_by_username(username):
            raise ValueError("Username already exists")
        
        # Create user
        user = cls(
            username=username.lower(),
            email=email.lower(),
            **kwargs
        )
        user.set_password(password)
        
        return user
    
    # =============================================================================
    # REPR
    # =============================================================================
    
    def __repr__(self):
        return f'<User {self.username}>'