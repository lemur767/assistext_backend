


from app.extensions import db
from datetime import datetime, timedelta
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy import Index
import uuid
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token, create_refresh_token

# =============================================================================
# USER MANAGEMENT MODELS
# =============================================================================

class User(db.Model):
    """
    Core user model with comprehensive authentication and subscription management
    Supports trial periods, subscription tracking, and SignalWire integration
    """
    __tablename__ = 'users'

    # Primary Key
    id = db.Column(db.Integer, primary_key=True)
    
    # Authentication
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    
    # Profile Information
    first_name = db.Column(db.String(50))
    last_name = db.Column(db.String(50))
    phone_number = db.Column(db.String(20))
    timezone = db.Column(db.String(50), default='UTC')
    
    # Account Status
    is_active = db.Column(db.Boolean, default=True)
    is_admin = db.Column(db.Boolean, default=False)
    email_verified = db.Column(db.Boolean, default=False)
    email_verification_token = db.Column(db.String(255))
    
    # Trial Management
    is_trial_eligible = db.Column(db.Boolean, default=True)
    trial_status = db.Column(db.String(20), default='pending')  # pending, active, expired, converted
    trial_started_at = db.Column(db.DateTime)
    trial_ends_at = db.Column(db.DateTime)
    trial_warning_sent = db.Column(db.Boolean, default=False)
    
    # SignalWire Integration
    signalwire_subproject_id = db.Column(db.String(100))
    signalwire_phone_number = db.Column(db.String(20))
    signalwire_phone_number_sid = db.Column(db.String(100))
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    last_activity = db.Column(db.DateTime)
    
    # Relationships
    subscription = db.relationship('Subscription', back_populates='user', uselist=False)
    clients = db.relationship('Client', back_populates='user', lazy='dynamic')
    messages = db.relationship('Message', back_populates='user', lazy='dynamic')
    usage_records = db.relationship('UsageRecord', back_populates='user', lazy='dynamic')
    payment_methods = db.relationship('PaymentMethod', back_populates='user', lazy='dynamic')
    
    def __init__(self, username, email, password, **kwargs):
        self.username = username
        self.email = email
        self.set_password(password)
        for key, value in kwargs.items():
            setattr(self, key, value)
    
    def set_password(self, password):
        """Hash and set password"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Check password against hash"""
        return check_password_hash(self.password_hash, password)
    
    def generate_tokens(self):
        """Generate JWT access and refresh tokens"""
        additional_claims = {
            'user_id': self.id,
            'username': self.username,
            'trial_status': self.trial_status,
            'subscription_status': self.subscription.status if self.subscription else None
        }
        
        access_token = create_access_token(
            identity=self.id,
            additional_claims=additional_claims
        )
        refresh_token = create_refresh_token(identity=self.id)
        
        return {
            'access_token': access_token,
            'refresh_token': refresh_token,
            'expires_in': 3600  # 1 hour
        }
    
    def start_trial(self):
        """Start 14-day trial period"""
        if not self.is_trial_eligible:
            raise ValueError("User not eligible for trial")
        
        self.trial_status = 'active'
        self.trial_started_at = datetime.utcnow()
        self.trial_ends_at = datetime.utcnow() + timedelta(days=14)
        self.is_trial_eligible = False
        
        db.session.commit()
    
    def is_trial_expired(self):
        """Check if trial has expired"""
        return (self.trial_status == 'active' and 
                self.trial_ends_at and 
                datetime.utcnow() > self.trial_ends_at)
    
    def days_remaining_in_trial(self):
        """Get days remaining in trial"""
        if self.trial_status != 'active' or not self.trial_ends_at:
            return 0
        
        remaining = self.trial_ends_at - datetime.utcnow()
        return max(0, remaining.days)
    
    def to_dict(self, include_sensitive=False):
        """Convert to dictionary"""
        data = {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'phone_number': self.phone_number,
            'timezone': self.timezone,
            'is_active': self.is_active,
            'is_admin': self.is_admin,
            'email_verified': self.email_verified,
            'trial_status': self.trial_status,
            'trial_ends_at': self.trial_ends_at.isoformat() if self.trial_ends_at else None,
            'signalwire_phone_number': self.signalwire_phone_number,
            'created_at': self.created_at.isoformat(),
            'last_login': self.last_login.isoformat() if self.last_login else None
        }
        
        if include_sensitive:
            data.update({
                'signalwire_subproject_id': self.signalwire_subproject_id,
                'signalwire_phone_number_sid': self.signalwire_phone_number_sid
            })
        
        return data

# =============================================================================
# SUBSCRIPTION & BILLING MODELS  
# =============================================================================

class SubscriptionPlan(db.Model):
    """
    Subscription plans with feature definitions and pricing
    """
    __tablename__ = 'subscription_plans'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    status = db.Column(db.String(20), default='active')  # active, inactive, archived
    
    # Pricing
    monthly_price = db.Column(db.Float(10, 2), nullable=False)
    annual_price = db.Column(db.Float(10, 2))
    currency = db.Column(db.String(3), default='USD')
    setup_fee = db.Column(db.Float(10, 2), default=0)
    
    # Trial
    trial_period_days = db.Column(db.Integer, default=14)
    
    # Features (stored as JSON)
    features = db.Column(JSONB, nullable=False, default={})
    
    # Stripe Integration
    stripe_price_id_monthly = db.Column(db.String(100))
    stripe_price_id_annual = db.Column(db.String(100))
    stripe_product_id = db.Column(db.String(100))
    
    # Marketing
    popular = db.Column(db.Boolean, default=False)
    recommended = db.Column(db.Boolean, default=False)
    sort_order = db.Column(db.Integer, default=0)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    subscriptions = db.relationship('Subscription', back_populates='plan', lazy='dynamic')
    
    def to_dict(self):
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
            'features': self.features,
            'popular': self.popular,
            'recommended': self.recommended,
            'created_at': self.created_at.isoformat()
        }

class Subscription(db.Model):

    
   
    __tablename__ = 'subscriptions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
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
    amount = db.Column(db.Float(10, 2), nullable=False)
    currency = db.Column(db.String(3), default='USD')
    
    # Stripe Integration
    stripe_subscription_id = db.Column(db.String(100), unique=True)
    stripe_customer_id = db.Column(db.String(100))
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', back_populates='subscription')
    plan = db.relationship('SubscriptionPlan', back_populates='subscriptions')
    usage_records = db.relationship('UsageRecord', back_populates='subscription', lazy='dynamic')
    invoices = db.relationship('Invoice', back_populates='subscription', lazy='dynamic')
    
    def is_active(self):
        """Check if subscription is currently active"""
        return self.status in ['active', 'trialing'] and datetime.utcnow() < self.current_period_end
    
    def days_until_renewal(self):
        """Get days until next renewal"""
        if not self.current_period_end:
            return 0
        remaining = self.current_period_end - datetime.utcnow()
        return max(0, remaining.days)
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'plan_id': self.plan_id,
            'status': self.status,
            'billing_cycle': self.billing_cycle,
            'auto_renew': self.auto_renew,
            'current_period_start': self.current_period_start.isoformat(),
            'current_period_end': self.current_period_end.isoformat(),
            'trial_end': self.trial_end.isoformat() if self.trial_end else None,
            'amount': float(self.amount),
            'currency': self.currency,
            'created_at': self.created_at.isoformat(),
            'plan': self.plan.to_dict() if self.plan else None
        }

class PaymentMethod(db.Model):

    __tablename__ = 'payment_methods'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Payment Method Details
    type = db.Column(db.String(20), nullable=False)  # card, bank, paypal
    is_default = db.Column(db.Boolean, default=False)
    
    # Card Details (masked for security)
    card_brand = db.Column(db.String(20))
    card_last4 = db.Column(db.String(4))
    card_exp_month = db.Column(db.Integer)
    card_exp_year = db.Column(db.Integer)
    
    # Stripe Integration
    stripe_payment_method_id = db.Column(db.String(100), unique=True)
    
    # Status
    status = db.Column(db.String(20), default='active')  # active, expired, invalid
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_used_at = db.Column(db.DateTime)
    
    # Relationships
    user = db.relationship('User', back_populates='payment_methods')
    
    def to_dict(self):
        return {
            'id': self.id,
            'type': self.type,
            'is_default': self.is_default,
            'card_brand': self.card_brand,
            'card_last4': self.card_last4,
            'card_exp_month': self.card_exp_month,
            'card_exp_year': self.card_exp_year,
            'status': self.status,
            'created_at': self.created_at.isoformat(),
            'last_used_at': self.last_used_at.isoformat() if self.last_used_at else None
        }

# =============================================================================
# CLIENT & MESSAGING MODELS
# =============================================================================

class Client(db.Model):
  
    __tablename__ = 'clients'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Client Information
    phone_number = db.Column(db.String(20), nullable=False, index=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(120))
    notes = db.Column(db.Text)
    
    # Status and Tags
    status = db.Column(db.String(20), default='active')  # active, blocked, archived
    tags = db.Column(JSONB, default=[])
    
    # Conversation Stats
    total_messages = db.Column(db.Integer, default=0)
    last_message_at = db.Column(db.DateTime)
    last_message_preview = db.Column(db.String(200))
    unread_count = db.Column(db.Integer, default=0)
    
    # AI Settings
    ai_enabled = db.Column(db.Boolean, default=True)
    ai_personality = db.Column(db.String(50), default='professional')
    custom_ai_prompt = db.Column(db.Text)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', back_populates='clients')
    messages = db.relationship('Message', back_populates='client', lazy='dynamic')
    
    __table_args__ = (
        Index('ix_clients_user_phone', 'user_id', 'phone_number'),
        db.UniqueConstraint('user_id', 'phone_number', name='unique_user_client_phone'),
    )
    
    def to_dict(self, include_stats=False):
        data = {
            'id': self.id,
            'phone_number': self.phone_number,
            'name': self.name,
            'email': self.email,
            'notes': self.notes,
            'status': self.status,
            'tags': self.tags,
            'ai_enabled': self.ai_enabled,
            'ai_personality': self.ai_personality,
            'created_at': self.created_at.isoformat()
        }
        
        if include_stats:
            data.update({
                'total_messages': self.total_messages,
                'last_message_at': self.last_message_at.isoformat() if self.last_message_at else None,
                'last_message_preview': self.last_message_preview,
                'unread_count': self.unread_count
            })
        
        return data

class Message(db.Model):
   
    __tablename__ = 'messages'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)
    
    # Message Content
    body = db.Column(db.Text, nullable=False)
    from_number = db.Column(db.String(20), nullable=False)
    to_number = db.Column(db.String(20), nullable=False)
    
    # Message Metadata
    direction = db.Column(db.String(10), nullable=False)  # inbound, outbound
    is_read = db.Column(db.Boolean, default=False)
    is_flagged = db.Column(db.Boolean, default=False)
    flag_reasons = db.Column(JSONB, default=[])
    
    # AI Integration
    ai_generated = db.Column(db.Boolean, default=False)
    ai_model = db.Column(db.String(50))
    ai_prompt_used = db.Column(db.Text)
    ai_confidence_score = db.Column(db.Float)
    human_reviewed = db.Column(db.Boolean, default=False)
    
    # SignalWire Integration
    signalwire_message_sid = db.Column(db.String(100), unique=True)
    signalwire_status = db.Column(db.String(20))  # queued, sending, sent, delivered, failed
    signalwire_error_code = db.Column(db.String(20))
    signalwire_error_message = db.Column(db.Text)
    
    # Media Support
    media_urls = db.Column(JSONB, default=[])
    media_count = db.Column(db.Integer, default=0)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    sent_at = db.Column(db.DateTime)
    delivered_at = db.Column(db.DateTime)
    
    # Relationships
    user = db.relationship('User', back_populates='messages')
    client = db.relationship('Client', back_populates='messages')
    
    __table_args__ = (
        Index('ix_messages_user_created', 'user_id', 'created_at'),
        Index('ix_messages_client_created', 'client_id', 'created_at'),
        Index('ix_messages_signalwire_sid', 'signalwire_message_sid'),
    )
    
    def to_dict(self, include_ai_details=False):
        data = {
            'id': self.id,
            'client_id': self.client_id,
            'body': self.body,
            'from_number': self.from_number,
            'to_number': self.to_number,
            'direction': self.direction,
            'is_read': self.is_read,
            'is_flagged': self.is_flagged,
            'ai_generated': self.ai_generated,
            'signalwire_status': self.signalwire_status,
            'media_count': self.media_count,
            'created_at': self.created_at.isoformat(),
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'delivered_at': self.delivered_at.isoformat() if self.delivered_at else None
        }
        
        if include_ai_details and self.ai_generated:
            data.update({
                'ai_model': self.ai_model,
                'ai_confidence_score': self.ai_confidence_score,
                'human_reviewed': self.human_reviewed
            })
        
        return data

# =============================================================================
# USAGE TRACKING MODELS
# =============================================================================

class UsageRecord(db.Model):
   
    __tablename__ = 'usage_records'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    subscription_id = db.Column(db.Integer, db.ForeignKey('subscriptions.id'))
    
    # Usage Details
    metric_type = db.Column(db.String(50), nullable=False)  # sms_sent, sms_received, ai_responses, etc.
    quantity = db.Column(db.Integer, default=1)
    unit_cost = db.Column(db.Float(10, 4))
    total_cost = db.Column(db.Float(10, 2))
    
    # Reference Information
    resource_id = db.Column(db.String(100))  # Message ID, etc.
    resource_type = db.Column(db.String(50))  # message, ai_response, etc.
    
    # Metadata
    useage_metadata = db.Column(JSONB, default={})
    
    # Billing Period
    billing_period_start = db.Column(db.DateTime, nullable=False)
    billing_period_end = db.Column(db.DateTime, nullable=False)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    user = db.relationship('User', back_populates='usage_records')
    subscription = db.relationship('Subscription', back_populates='usage_records')
    
    __table_args__ = (
        Index('ix_usage_user_period', 'user_id', 'billing_period_start', 'billing_period_end'),
        Index('ix_usage_subscription_period', 'subscription_id', 'billing_period_start'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'metric_type': self.metric_type,
            'quantity': self.quantity,
            'unit_cost': float(self.unit_cost) if self.unit_cost else None,
            'total_cost': float(self.total_cost) if self.total_cost else None,
            'resource_type': self.resource_type,
            'billing_period_start': self.billing_period_start.isoformat(),
            'billing_period_end': self.billing_period_end.isoformat(),
            'created_at': self.created_at.isoformat(),
            'useage_metadata': self.useage_metadata
        }

# =============================================================================
# INVOICE & BILLING MODELS
# =============================================================================

class Invoice(db.Model):
  
    __tablename__ = 'invoices'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    subscription_id = db.Column(db.Integer, db.ForeignKey('subscriptions.id'))
    
    # Invoice Details
    invoice_number = db.Column(db.String(50), unique=True, nullable=False)
    status = db.Column(db.String(20), nullable=False)  # draft, open, paid, void
    
    # Amounts
    subtotal = db.Column(db.Float(10, 2), nullable=False)
    tax_amount = db.Column(db.Float(10, 2), default=0)
    discount_amount = db.Column(db.Float(10, 2), default=0)
    total = db.Column(db.Float(10, 2), nullable=False)
    amount_paid = db.Column(db.Float(10, 2), default=0)
    currency = db.Column(db.String(3), default='USD')
    
    # Dates
    due_date = db.Column(db.DateTime, nullable=False)
    paid_at = db.Column(db.DateTime)
    
    # Stripe Integration
    stripe_invoice_id = db.Column(db.String(100), unique=True)
    
    # Files
    pdf_path = db.Column(db.String(255))
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User')
    subscription = db.relationship('Subscription', back_populates='invoices')
    
    def to_dict(self):
        return {
            'id': self.id,
            'invoice_number': self.invoice_number,
            'status': self.status,
            'subtotal': float(self.subtotal),
            'tax_amount': float(self.tax_amount),
            'discount_amount': float(self.discount_amount),
            'total': float(self.total),
            'amount_paid': float(self.amount_paid),
            'currency': self.currency,
            'due_date': self.due_date.isoformat(),
            'paid_at': self.paid_at.isoformat() if self.paid_at else None,
            'created_at': self.created_at.isoformat()
        }

# =============================================================================
# INDEXES FOR PERFORMANCE
# =============================================================================

# Additional indexes for common queries
Index('ix_users_email_active', User.email, User.is_active)
Index('ix_users_trial_status', User.trial_status, User.trial_ends_at)
Index('ix_subscriptions_user_status', Subscription.user_id, Subscription.status)
Index('ix_messages_numbers_date', Message.from_number, Message.to_number, Message.created_at)