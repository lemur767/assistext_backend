# app/core/models.py
"""
CONSOLIDATED DATABASE MODELS - CORRECTED VERSION
All models in one file with PostgreSQL, Stripe integration, and SignalWire subprojects
"""
from app.extensions import db
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token, create_refresh_token
import uuid


# =============================================================================
# BASE MODEL WITH COMMON PATTERNS
# =============================================================================

class BaseModel(db.Model):
    """Base model with common fields and methods"""
    __abstract__ = True
    
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    def to_dict(self, exclude=None):
        """Convert model to dictionary with consistent formatting"""
        exclude = exclude or []
        result = {}
        for column in self.__table__.columns:
            if column.name not in exclude:
                value = getattr(self, column.name)
                if isinstance(value, datetime):
                    result[column.name] = value.isoformat()
                elif hasattr(value, '__float__'):
                    result[column.name] = float(value)
                else:
                    result[column.name] = value
        return result
    
    def save(self):
        """Save model to database"""
        db.session.add(self)
        db.session.commit()
        return self
    
    def delete(self):
        """Delete model from database"""
        db.session.delete(self)
        db.session.commit()


# =============================================================================
# USER & AUTHENTICATION MODELS
# =============================================================================

class User(BaseModel):
    """User model with Stripe and SignalWire integration"""
    __tablename__ = 'users'
    
    # Authentication
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    
    # Personal Information
    first_name = db.Column(db.String(50))
    last_name = db.Column(db.String(50))
    display_name = db.Column(db.String(100))
    personal_phone = db.Column(db.String(20))
    timezone = db.Column(db.String(50), default='UTC')
    
    # Account Status & Permissions
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    last_login = db.Column(db.DateTime)
    
    # Trial & Billing Status
    is_trial_eligible = db.Column(db.Boolean, default=True)
    trial_status = db.Column(db.String(20), default='pending_payment')  # pending_payment, active, expired, converted
    trial_warning_sent = db.Column(db.Boolean, default=False)
    payment_validated_at = db.Column(db.DateTime)
    trial_started_at = db.Column(db.DateTime)
    trial_expires_at = db.Column(db.DateTime)
    trial_signalwire_setup = db.Column(db.Boolean, default=False)
    
    # SignalWire Subproject Integration
    signalwire_subproject_sid = db.Column(db.String(100), unique=True, index=True)  # SignalWire subproject ID
    signalwire_friendly_name = db.Column(db.String(200))  # username_userid format
    selected_phone_number = db.Column(db.String(20), unique=True, index=True)  # User's SignalWire number
    signalwire_phone_sid = db.Column(db.String(100))  # Phone number SID in SignalWire
    preferred_area_code = db.Column(db.String(10))
    preferred_country = db.Column(db.String(2), default='US')
    preferred_region = db.Column(db.String(50))
    preferred_city = db.Column(db.String(100))
    
    # Stripe Integration
    stripe_customer_id = db.Column(db.String(100), unique=True, index=True)  # Stripe customer ID
    stripe_setup_complete = db.Column(db.Boolean, default=False)
    
    # AI Settings
    ai_enabled = db.Column(db.Boolean, default=True)
    ai_personality = db.Column(db.Text)
    ai_response_style = db.Column(db.String(20), default='professional')
    ai_language = db.Column(db.String(10), default='en')
    use_emojis = db.Column(db.Boolean, default=False)
    casual_language = db.Column(db.Boolean, default=False)
    custom_instructions = db.Column(db.Text)
    
    # Auto-Reply Settings
    auto_reply_enabled = db.Column(db.Boolean, default=True)
    custom_greeting = db.Column(db.Text)
    out_of_office_enabled = db.Column(db.Boolean, default=False)
    out_of_office_message = db.Column(db.Text)
    out_of_office_start = db.Column(db.DateTime)
    out_of_office_end = db.Column(db.DateTime)
    
    # Business Hours
    business_hours_enabled = db.Column(db.Boolean, default=False)
    business_hours_start = db.Column(db.Time)
    business_hours_end = db.Column(db.Time)
    business_days = db.Column(db.String(20))  # Comma-separated days: "1,2,3,4,5"
    after_hours_message = db.Column(db.Text)
    
    # Security & Moderation
    enable_flagged_word_detection = db.Column(db.Boolean, default=True)
    custom_flagged_words = db.Column(db.Text)
    
    # Usage Tracking & Limits
    daily_ai_response_count = db.Column(db.Integer, default=0)
    daily_ai_response_limit = db.Column(db.Integer, default=100)  # Trial limit
    last_ai_response_reset = db.Column(db.Date, default=datetime.utcnow().date)
    
    # Relationships
    messages = db.relationship('Message', back_populates='user', lazy='dynamic', cascade='all, delete-orphan')
    clients = db.relationship('Client', back_populates='user', lazy='dynamic', cascade='all, delete-orphan')
    subscriptions = db.relationship('Subscription', back_populates='user', lazy='dynamic')
    payments = db.relationship('Payment', back_populates='user', lazy='dynamic')
    usage_records = db.relationship('UsageRecord', back_populates='user', lazy='dynamic')
    api_keys = db.relationship('APIKey', back_populates='user', lazy='dynamic', cascade='all, delete-orphan')
    activity_logs = db.relationship('ActivityLog', back_populates='user', lazy='dynamic')
    trial_notifications = db.relationship('TrialNotification', back_populates='user', lazy='dynamic')
    
    def set_password(self, password):
        """Set password hash"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Check password against hash"""
        return check_password_hash(self.password_hash, password)
    
    def generate_tokens(self):
        """Generate access and refresh tokens"""
        return {
            'access_token': create_access_token(identity=self.id),
            'refresh_token': create_refresh_token(identity=self.id)
        }
    
    def to_dict(self, exclude=None):
        """Override to exclude sensitive fields by default"""
        exclude = exclude or ['password_hash']
        return super().to_dict(exclude=exclude)
    
    @property
    def full_name(self):
        """Get user's full name"""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.display_name or self.username
    
    @property
    def is_trial_active(self):
        """Check if trial is currently active"""
        return (self.trial_status == 'active' and 
                self.trial_expires_at and 
                self.trial_expires_at > datetime.utcnow())
    
    @property
    def signalwire_subproject_name(self):
        """Generate SignalWire subproject friendly name"""
        return f"{self.username}_{self.id}"
    
    def can_make_ai_response(self):
        """Check if user can make AI response (within limits)"""
        today = datetime.utcnow().date()
        
        # Reset daily counter if it's a new day
        if self.last_ai_response_reset != today:
            self.daily_ai_response_count = 0
            self.last_ai_response_reset = today
            db.session.commit()
        
        return self.daily_ai_response_count < self.daily_ai_response_limit
    
    def increment_ai_response_count(self):
        """Increment daily AI response count"""
        self.daily_ai_response_count += 1
        db.session.commit()
    
    def __repr__(self):
        return f'<User {self.username}>'


# =============================================================================
# STRIPE BILLING MODELS
# =============================================================================

class SubscriptionPlan(BaseModel):
    """Stripe subscription plan definitions"""
    __tablename__ = 'subscription_plans'
    
    # Basic Plan Info
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    status = db.Column(db.String(20), default='active')  # active, inactive, archived
    
    # Pricing
    monthly_price = db.Column(db.Numeric(10, 2), nullable=False)
    annual_price = db.Column(db.Numeric(10, 2))
    currency = db.Column(db.String(3), default='USD')
    setup_fee = db.Column(db.Numeric(10, 2), default=0.00)
    trial_period_days = db.Column(db.Integer, default=14)
    
    # Limits & Features
    sms_limit_monthly = db.Column(db.Integer, default=1000)
    voice_minutes_limit = db.Column(db.Integer, default=100)
    client_limit = db.Column(db.Integer, default=100)
    ai_response_limit_daily = db.Column(db.Integer, default=500)
    features = db.Column(db.Text)  # JSON string of features
    
    # Stripe Integration
    stripe_price_id_monthly = db.Column(db.String(100))  # Stripe monthly price ID
    stripe_price_id_annual = db.Column(db.String(100))   # Stripe annual price ID
    stripe_product_id = db.Column(db.String(100))        # Stripe product ID
    
    # Marketing
    popular = db.Column(db.Boolean, default=False)
    recommended = db.Column(db.Boolean, default=False)
    sort_order = db.Column(db.Integer, default=0)
    
    # Relationships
    subscriptions = db.relationship('Subscription', back_populates='plan', lazy='dynamic')
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'status': self.status,
            'monthly_price': float(self.monthly_price),
            'annual_price': float(self.annual_price) if self.annual_price else None,
            'currency': self.currency,
            'setup_fee': float(self.setup_fee),
            'trial_period_days': self.trial_period_days,
            'sms_limit_monthly': self.sms_limit_monthly,
            'voice_minutes_limit': self.voice_minutes_limit,
            'client_limit': self.client_limit,
            'ai_response_limit_daily': self.ai_response_limit_daily,
            'features': self.features,
            'popular': self.popular,
            'recommended': self.recommended,
            'stripe_product_id': self.stripe_product_id,
            'stripe_price_id_monthly': self.stripe_price_id_monthly,
            'stripe_price_id_annual': self.stripe_price_id_annual,
            'created_at': self.created_at.isoformat()
        }


class Subscription(BaseModel):
    """User subscription records with Stripe integration"""
    __tablename__ = 'subscriptions'
    
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    plan_id = db.Column(db.Integer, db.ForeignKey('subscription_plans.id'), nullable=False)
    
    # Subscription Details
    status = db.Column(db.String(20), nullable=False)  # active, canceled, past_due, unpaid, trialing
    billing_cycle = db.Column(db.String(10), nullable=False)  # monthly, annual
    auto_renew = db.Column(db.Boolean, default=True)
    
    # Dates
    current_period_start = db.Column(db.DateTime, nullable=False)
    current_period_end = db.Column(db.DateTime, nullable=False)
    trial_end = db.Column(db.DateTime)
    canceled_at = db.Column(db.DateTime)
    ended_at = db.Column(db.DateTime)
    
    # Financial
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    currency = db.Column(db.String(3), default='USD')
    
    # Stripe Integration
    stripe_subscription_id = db.Column(db.String(100), unique=True, index=True)
    stripe_customer_id = db.Column(db.String(100), index=True)
    
    # Relationships
    user = db.relationship('User', back_populates='subscriptions')
    plan = db.relationship('SubscriptionPlan', back_populates='subscriptions')
    payments = db.relationship('Payment', back_populates='subscription', lazy='dynamic')


class PaymentMethod(BaseModel):
    """User payment methods for Stripe"""
    __tablename__ = 'payment_methods'
    
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    
    # Payment Details
    payment_type = db.Column(db.String(20), nullable=False)  # card, bank_account
    last_four = db.Column(db.String(4))
    brand = db.Column(db.String(20))  # visa, mastercard, etc.
    exp_month = db.Column(db.Integer)
    exp_year = db.Column(db.Integer)
    is_default = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    
    # Stripe Integration
    stripe_payment_method_id = db.Column(db.String(100), unique=True, nullable=False)
    
    # Relationships
    user = db.relationship('User')


class Payment(BaseModel):
    """Payment transaction records with Stripe integration"""
    __tablename__ = 'payments'
    
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    subscription_id = db.Column(db.Integer, db.ForeignKey('subscriptions.id'), index=True)
    
    # Payment Details
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    currency = db.Column(db.String(3), default='USD')
    status = db.Column(db.String(20), nullable=False)  # pending, succeeded, failed, refunded
    description = db.Column(db.String(255))
    
    # Stripe Integration
    stripe_payment_intent_id = db.Column(db.String(100), unique=True, index=True)
    stripe_invoice_id = db.Column(db.String(100))
    stripe_charge_id = db.Column(db.String(100))
    
    # Timestamps
    processed_at = db.Column(db.DateTime)
    
    # Relationships
    user = db.relationship('User', back_populates='payments')
    subscription = db.relationship('Subscription', back_populates='payments')


class Invoice(BaseModel):
    """Invoice records with Stripe integration"""
    __tablename__ = 'invoices'
    
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    subscription_id = db.Column(db.Integer, db.ForeignKey('subscriptions.id'), index=True)
    
    # Invoice Details
    invoice_number = db.Column(db.String(50), unique=True, nullable=False)
    amount_due = db.Column(db.Numeric(10, 2), nullable=False)
    amount_paid = db.Column(db.Numeric(10, 2), default=0)
    currency = db.Column(db.String(3), default='USD')
    status = db.Column(db.String(20), default='draft')  # draft, open, paid, void, uncollectible
    
    # Dates
    due_date = db.Column(db.DateTime, nullable=False)
    paid_at = db.Column(db.DateTime)
    
    # Stripe Integration
    stripe_invoice_id = db.Column(db.String(100), unique=True, index=True)
    
    # File Storage
    pdf_path = db.Column(db.String(255))
    
    # Relationships
    user = db.relationship('User')
    subscription = db.relationship('Subscription')
    items = db.relationship('InvoiceItem', back_populates='invoice', lazy='dynamic', cascade='all, delete-orphan')


class InvoiceItem(BaseModel):
    """Invoice line items"""
    __tablename__ = 'invoice_items'
    
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'), nullable=False, index=True)
    
    # Item Details
    description = db.Column(db.String(255), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    
    # Relationships
    invoice = db.relationship('Invoice', back_populates='items')


# =============================================================================
# SIGNALWIRE SUBPROJECT MODELS
# =============================================================================

class SignalWireSubproject(BaseModel):
    """Track SignalWire subprojects for each user"""
    __tablename__ = 'signalwire_subprojects'
    
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True, index=True)
    
    # SignalWire Details
    subproject_sid = db.Column(db.String(100), unique=True, nullable=False, index=True)
    friendly_name = db.Column(db.String(200), nullable=False)  # username_userid format
    auth_token = db.Column(db.String(100))  # Subproject auth token
    
    # Status & Configuration
    status = db.Column(db.String(20), default='active')  # active, suspended, deleted
    webhook_configured = db.Column(db.Boolean, default=False)
    
    # Usage & Limits
    sms_sent_count = db.Column(db.Integer, default=0)
    sms_received_count = db.Column(db.Integer, default=0)
    voice_minutes_used = db.Column(db.Integer, default=0)
    
    # Trial & Billing
    trial_active = db.Column(db.Boolean, default=True)
    trial_expires_at = db.Column(db.DateTime)
    suspended_for_payment = db.Column(db.Boolean, default=False)
    
    # Relationships
    user = db.relationship('User')
    phone_numbers = db.relationship('SignalWirePhoneNumber', back_populates='subproject', lazy='dynamic')


class SignalWirePhoneNumber(BaseModel):
    """Track phone numbers assigned to subprojects"""
    __tablename__ = 'signalwire_phone_numbers'
    
    subproject_id = db.Column(db.Integer, db.ForeignKey('signalwire_subprojects.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    
    # Phone Number Details
    phone_number = db.Column(db.String(20), unique=True, nullable=False, index=True)
    phone_number_sid = db.Column(db.String(100), unique=True, nullable=False)
    friendly_name = db.Column(db.String(200))
    
    # Capabilities
    sms_enabled = db.Column(db.Boolean, default=True)
    voice_enabled = db.Column(db.Boolean, default=True)
    mms_enabled = db.Column(db.Boolean, default=True)
    
    # Configuration
    sms_webhook_url = db.Column(db.String(500))
    voice_webhook_url = db.Column(db.String(500))
    status_webhook_url = db.Column(db.String(500))
    
    # Status
    status = db.Column(db.String(20), default='active')  # active, suspended, released
    purchased_at = db.Column(db.DateTime, default=datetime.utcnow)
    released_at = db.Column(db.DateTime)
    
    # Relationships
    subproject = db.relationship('SignalWireSubproject', back_populates='phone_numbers')
    user = db.relationship('User')


# =============================================================================
# MESSAGING MODELS
# =============================================================================

class Client(BaseModel):
    """Client model for managing customer contacts"""
    __tablename__ = 'clients'
    
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    phone_number = db.Column(db.String(20), nullable=False, index=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(120))
    notes = db.Column(db.Text)
    tags = db.Column(db.String(500))  # Comma-separated tags
    is_blocked = db.Column(db.Boolean, default=False)
    last_contact = db.Column(db.DateTime)
    
    # Relationships
    user = db.relationship('User', back_populates='clients')
    messages = db.relationship('Message', back_populates='client', lazy='dynamic')
    
    def __repr__(self):
        return f'<Client {self.phone_number}>'


class Message(BaseModel):
    """Message model for SMS/chat history"""
    __tablename__ = 'messages'
    
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), index=True)
    
    # Message Content
    from_number = db.Column(db.String(20), nullable=False, index=True)
    to_number = db.Column(db.String(20), nullable=False, index=True)
    body = db.Column(db.Text, nullable=False)
    direction = db.Column(db.String(10), nullable=False)  # 'inbound' or 'outbound'
    
    # SignalWire Integration
    signalwire_sid = db.Column(db.String(100), unique=True, index=True)
    signalwire_subproject_sid = db.Column(db.String(100))  # Which subproject handled this
    status = db.Column(db.String(20), default='pending')  # pending, sent, delivered, failed
    error_code = db.Column(db.String(10))
    error_message = db.Column(db.String(255))
    
    # AI Processing
    ai_generated = db.Column(db.Boolean, default=False)
    ai_model_used = db.Column(db.String(50))  # Which AI model generated response
    ai_confidence = db.Column(db.Float)
    ai_processing_time_ms = db.Column(db.Integer)
    flagged = db.Column(db.Boolean, default=False)
    flagged_reason = db.Column(db.String(255))
    
    # Timestamps
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)
    delivered_at = db.Column(db.DateTime)
    
    # Relationships
    user = db.relationship('User', back_populates='messages')
    client = db.relationship('Client', back_populates='messages')
    
    def __repr__(self):
        return f'<Message {self.from_number} -> {self.to_number}>'


# =============================================================================
# USAGE & ANALYTICS MODELS
# =============================================================================

class UsageRecord(BaseModel):
    """Usage tracking for billing and analytics"""
    __tablename__ = 'usage_records'
    
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    
    # Usage Details
    usage_type = db.Column(db.String(20), nullable=False, index=True)  # sms_sent, sms_received, voice_minutes, ai_responses
    quantity = db.Column(db.Integer, default=1)
    cost = db.Column(db.Numeric(10, 4))  # Cost in cents/dollars
    
    # SignalWire Integration
    signalwire_subproject_sid = db.Column(db.String(100))
    signalwire_message_sid = db.Column(db.String(100))
    
    # Metadata
    metadata = db.Column(db.Text)  # JSON string for additional data
    billing_period = db.Column(db.String(20))  # YYYY-MM format
    
    # Relationships
    user = db.relationship('User', back_populates='usage_records')


class UsageOverage(BaseModel):
    """Track usage overages for billing"""
    __tablename__ = 'usage_overages'
    
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    subscription_id = db.Column(db.Integer, db.ForeignKey('subscriptions.id'), nullable=False)
    
    # Overage Details
    usage_type = db.Column(db.String(20), nullable=False)
    overage_quantity = db.Column(db.Integer, nullable=False)
    overage_cost = db.Column(db.Numeric(10, 2), nullable=False)
    billing_period = db.Column(db.String(20), nullable=False)
    
    # Status
    billed = db.Column(db.Boolean, default=False)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'))
    
    # Relationships
    user = db.relationship('User')
    subscription = db.relationship('Subscription')


# =============================================================================
# UTILITY & ADMIN MODELS
# =============================================================================

class APIKey(BaseModel):
    """API keys for user access"""
    __tablename__ = 'api_keys'
    
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    
    # Key Details
    name = db.Column(db.String(100), nullable=False)
    key_hash = db.Column(db.String(255), nullable=False, unique=True)
    key_prefix = db.Column(db.String(20), nullable=False)  # First few chars for display
    permissions = db.Column(db.String(500))  # Comma-separated permissions
    is_active = db.Column(db.Boolean, default=True)
    last_used_at = db.Column(db.DateTime)
    expires_at = db.Column(db.DateTime)
    
    # Relationships
    user = db.relationship('User', back_populates='api_keys')


class ActivityLog(BaseModel):
    """Activity logging for audit trails"""
    __tablename__ = 'activity_logs'
    
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)
    
    # Activity Details
    action = db.Column(db.String(100), nullable=False, index=True)
    resource_type = db.Column(db.String(50), index=True)
    resource_id = db.Column(db.String(50))
    details = db.Column(db.Text)  # JSON string
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(500))
    
    # Relationships
    user = db.relationship('User', back_populates='activity_logs')


class NotificationSetting(BaseModel):
    """User notification preferences"""
    __tablename__ = 'notification_settings'
    
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True)
    
    # Email Notifications
    email_notifications = db.Column(db.Boolean, default=True)
    billing_reminders = db.Column(db.Boolean, default=True)
    usage_alerts = db.Column(db.Boolean, default=True)
    security_alerts = db.Column(db.Boolean, default=True)
    marketing_emails = db.Column(db.Boolean, default=False)
    trial_warnings = db.Column(db.Boolean, default=True)
    
    # SMS Notifications
    sms_notifications = db.Column(db.Boolean, default=False)
    emergency_contact = db.Column(db.String(20))
    
    # Relationships
    user = db.relationship('User')


class NotificationLog(BaseModel):
    """Log of sent notifications"""
    __tablename__ = 'notification_logs'
    
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    
    # Notification Details
    notification_type = db.Column(db.String(50), nullable=False, index=True)
    channel = db.Column(db.String(20), nullable=False)  # email, sms, push
    recipient = db.Column(db.String(255), nullable=False)
    subject = db.Column(db.String(255))
    content = db.Column(db.Text)
    
    # Status
    status = db.Column(db.String(20), default='pending')  # pending, sent, delivered, failed
    sent_at = db.Column(db.DateTime)
    delivered_at = db.Column(db.DateTime)
    error_message = db.Column(db.String(500))
    
    # External IDs
    external_id = db.Column(db.String(100))  # Email service ID, SMS service ID, etc.
    
    # Relationships
    user = db.relationship('User')


class TrialNotification(BaseModel):
    """Track trial-related notifications"""
    __tablename__ = 'trial_notifications'
    
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    
    # Notification Details
    notification_type = db.Column(db.String(50), nullable=False)  # welcome, warning, expired, etc.
    title = db.Column(db.String(200))
    message = db.Column(db.Text)
    priority = db.Column(db.String(20), default='medium')  # low, medium, high
    days_remaining = db.Column(db.Integer)
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)
    read_at = db.Column(db.DateTime)
    
    # Relationships
    user = db.relationship('User', back_populates='trial_notifications')