from app.extensions import db
from datetime import datetime
import json


class SubscriptionPlan(db.Model):
    __tablename__ = 'subscription_plans'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    price_monthly = db.Column(db.Numeric(10, 2))  # Monthly price in USD
    price_yearly = db.Column(db.Numeric(10, 2))   # Yearly price in USD
    stripe_price_id_monthly = db.Column(db.String(100))
    stripe_price_id_yearly = db.Column(db.String(100))
    max_profiles = db.Column(db.Integer, default=1)
    max_ai_responses_per_month = db.Column(db.Integer)  # None = unlimited
    message_retention_days = db.Column(db.Integer, default=30)
    features = db.Column(db.Text)  # JSON string of features
    is_active = db.Column(db.Boolean, default=True)
    sort_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    subscriptions = db.relationship('Subscription', back_populates='plan', lazy='dynamic')
    
    def get_features(self):
        """Get features as a dictionary"""
        if not self.features:
            return {}
        try:
            return json.loads(self.features)
        except (json.JSONDecodeError, TypeError):
            return {}
    
    def set_features(self, features_dict):
        """Set features from a dictionary"""
        if features_dict:
            self.features = json.dumps(features_dict)
        else:
            self.features = None
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'price_monthly': float(self.price_monthly) if self.price_monthly else None,
            'price_yearly': float(self.price_yearly) if self.price_yearly else None,
            'stripe_price_id_monthly': self.stripe_price_id_monthly,
            'stripe_price_id_yearly': self.stripe_price_id_yearly,
            'max_profiles': self.max_profiles,
            'max_ai_responses_per_month': self.max_ai_responses_per_month,
            'message_retention_days': self.message_retention_days,
            'features': self.get_features(),
            'is_active': self.is_active,
            'sort_order': self.sort_order,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }


class Subscription(db.Model):
    __tablename__ = 'subscriptions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    plan_id = db.Column(db.Integer, db.ForeignKey('subscription_plans.id'), nullable=False)
    stripe_subscription_id = db.Column(db.String(100))
    stripe_customer_id = db.Column(db.String(100))
    status = db.Column(db.String(20), default='active')  # active, cancelled, past_due, etc.
    current_period_start = db.Column(db.DateTime)
    current_period_end = db.Column(db.DateTime)
    cancel_at_period_end = db.Column(db.Boolean, default=False)
    trial_start = db.Column(db.DateTime)
    trial_end = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Usage tracking
    profiles_used = db.Column(db.Integer, default=0)
    ai_responses_used = db.Column(db.Integer, default=0)
    monthly_ai_responses_used = db.Column(db.Integer, default=0)
    last_usage_reset = db.Column(db.DateTime, default=datetime.utcnow)
    
    # FIXED: Changed 'metadata' to 'subscription_metadata'
    subscription_metadata = db.Column(db.Text)  # JSON string for flexible data
    
    # Relationships
    user = db.relationship('User', back_populates='subscriptions')
    plan = db.relationship('SubscriptionPlan', back_populates='subscriptions')
    invoices = db.relationship('Invoice', back_populates='subscription', lazy='dynamic')
    
    def get_subscription_metadata(self):
        """Get subscription metadata as dictionary"""
        if not self.subscription_metadata:
            return {}
        try:
            return json.loads(self.subscription_metadata)
        except (json.JSONDecodeError, TypeError):
            return {}
    
    def set_subscription_metadata(self, metadata_dict):
        """Set subscription metadata from dictionary"""
        if metadata_dict:
            self.subscription_metadata = json.dumps(metadata_dict)
        else:
            self.subscription_metadata = None
    
    def get_latest_invoice(self):
        """Get the most recent invoice for this subscription"""
        return self.invoices.order_by(Invoice.created_at.desc()).first()
    
    def get_unpaid_invoices(self):
        """Get all unpaid invoices for this subscription"""
        return self.invoices.filter(Invoice.status.in_(['open', 'past_due'])).all()
    
    def get_total_amount_due(self):
        """Get total amount due across all unpaid invoices"""
        unpaid = self.get_unpaid_invoices()
        return sum(float(invoice.get_balance_due()) for invoice in unpaid)
    
    def is_active(self):
        """Check if subscription is currently active"""
        return self.status == 'active' and (
            not self.current_period_end or 
            self.current_period_end > datetime.utcnow()
        )

    def is_trial(self):
        """Check if subscription is in trial period"""
        now = datetime.utcnow()
        return (self.trial_start and self.trial_end and
                self.trial_start <= now <= self.trial_end)

    def can_use_feature(self, feature_name):
        """Check if subscription allows usage of a specific feature"""
        if not self.is_active():
            return False
            
        plan_features = self.plan.get_features()
        return plan_features.get(feature_name, False)

    def get_usage_limits(self):
        """Get current usage limits for this subscription"""
        return {
            'max_profiles': self.plan.max_profiles,
            'max_ai_responses': self.plan.max_ai_responses_per_month,
            'profiles_used': self.profiles_used,
            'ai_responses_used': self.monthly_ai_responses_used,
            'profiles_remaining': max(0, self.plan.max_profiles - self.profiles_used),
            'ai_responses_remaining': max(0, self.plan.max_ai_responses_per_month - self.monthly_ai_responses_used) if self.plan.max_ai_responses_per_month else None
        }

    def reset_monthly_usage(self):
        """Reset monthly usage counters"""
        self.monthly_ai_responses_used = 0
        self.last_usage_reset = datetime.utcnow()
        db.session.commit()
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'plan_id': self.plan_id,
            'stripe_subscription_id': self.stripe_subscription_id,
            'stripe_customer_id': self.stripe_customer_id,
            'status': self.status,
            'current_period_start': self.current_period_start.isoformat() if self.current_period_start else None,
            'current_period_end': self.current_period_end.isoformat() if self.current_period_end else None,
            'cancel_at_period_end': self.cancel_at_period_end,
            'trial_start': self.trial_start.isoformat() if self.trial_start else None,
            'trial_end': self.trial_end.isoformat() if self.trial_end else None,
            'profiles_used': self.profiles_used,
            'ai_responses_used': self.ai_responses_used,
            'monthly_ai_responses_used': self.monthly_ai_responses_used,
            'last_usage_reset': self.last_usage_reset.isoformat() if self.last_usage_reset else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'subscription_metadata': self.get_subscription_metadata()
        }


class Invoice(db.Model):
    __tablename__ = 'invoices'
    
    id = db.Column(db.Integer, primary_key=True)
    subscription_id = db.Column(db.Integer, db.ForeignKey('subscriptions.id'), nullable=False)
    stripe_invoice_id = db.Column(db.String(100), unique=True)
    invoice_number = db.Column(db.String(50), unique=True, nullable=False)
    
    # Amount and currency
    amount_due = db.Column(db.Numeric(10, 2), nullable=False)
    amount_paid = db.Column(db.Numeric(10, 2), default=0)
    currency = db.Column(db.String(3), default='USD')
    tax_amount = db.Column(db.Numeric(10, 2), default=0)
    
    # Status and dates
    status = db.Column(db.String(20), default='draft')  # draft, open, paid, void, uncollectible
    billing_reason = db.Column(db.String(50))  # subscription_create, subscription_cycle, etc.
    
    # Important dates
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    period_start = db.Column(db.DateTime)
    period_end = db.Column(db.DateTime)
    due_date = db.Column(db.DateTime)
    paid_at = db.Column(db.DateTime)
    voided_at = db.Column(db.DateTime)
    
    # Additional details
    description = db.Column(db.Text)
    invoice_pdf_url = db.Column(db.String(500))  # URL to PDF from Stripe
    hosted_invoice_url = db.Column(db.String(500))  # Stripe hosted invoice page
    
    # FIXED: Changed 'metadata' to 'invoice_metadata'
    invoice_metadata = db.Column(db.Text)  # JSON string for flexible data storage
    
    # Relationships
    subscription = db.relationship('Subscription', back_populates='invoices')
    invoice_items = db.relationship('InvoiceItem', back_populates='invoice', cascade='all, delete-orphan')
    
    def get_invoice_metadata(self):
        """Get invoice metadata as a dictionary"""
        if not self.invoice_metadata:
            return {}
        try:
            return json.loads(self.invoice_metadata)
        except (json.JSONDecodeError, TypeError):
            return {}
    
    def set_invoice_metadata(self, metadata_dict):
        """Set invoice metadata from a dictionary"""
        if metadata_dict:
            self.invoice_metadata = json.dumps(metadata_dict)
        else:
            self.invoice_metadata = None
    
    def is_paid(self):
        """Check if invoice is fully paid"""
        return self.status == 'paid' and self.amount_paid >= self.amount_due
    
    def is_overdue(self):
        """Check if invoice is overdue"""
        if not self.due_date or self.is_paid():
            return False
        return datetime.utcnow() > self.due_date
    
    def get_balance_due(self):
        """Get remaining balance due"""
        return max(0, float(self.amount_due) - float(self.amount_paid or 0))
    
    def mark_as_paid(self, amount_paid=None, paid_at=None):
        """Mark invoice as paid"""
        self.amount_paid = amount_paid or self.amount_due
        self.paid_at = paid_at or datetime.utcnow()
        self.status = 'paid'
        db.session.commit()
    
    def to_dict(self):
        return {
            'id': self.id,
            'subscription_id': self.subscription_id,
            'stripe_invoice_id': self.stripe_invoice_id,
            'invoice_number': self.invoice_number,
            'amount_due': float(self.amount_due),
            'amount_paid': float(self.amount_paid or 0),
            'currency': self.currency,
            'tax_amount': float(self.tax_amount or 0),
            'status': self.status,
            'billing_reason': self.billing_reason,
            'created_at': self.created_at.isoformat(),
            'period_start': self.period_start.isoformat() if self.period_start else None,
            'period_end': self.period_end.isoformat() if self.period_end else None,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'paid_at': self.paid_at.isoformat() if self.paid_at else None,
            'voided_at': self.voided_at.isoformat() if self.voided_at else None,
            'description': self.description,
            'invoice_pdf_url': self.invoice_pdf_url,
            'hosted_invoice_url': self.hosted_invoice_url,
            'invoice_metadata': self.get_invoice_metadata(),
            'balance_due': self.get_balance_due(),
            'is_paid': self.is_paid(),
            'is_overdue': self.is_overdue()
        }


class InvoiceItem(db.Model):
    __tablename__ = 'invoice_items'
    
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'), nullable=False)
    stripe_invoice_item_id = db.Column(db.String(100))
    
    # Item details
    description = db.Column(db.String(500), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    unit_amount = db.Column(db.Numeric(10, 2), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    currency = db.Column(db.String(3), default='USD')
    
    # Period for subscription items
    period_start = db.Column(db.DateTime)
    period_end = db.Column(db.DateTime)
    
    # Proration and discounts
    proration = db.Column(db.Boolean, default=False)
    discount_amount = db.Column(db.Numeric(10, 2), default=0)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    invoice = db.relationship('Invoice', back_populates='invoice_items')
    
    def to_dict(self):
        return {
            'id': self.id,
            'invoice_id': self.invoice_id,
            'stripe_invoice_item_id': self.stripe_invoice_item_id,
            'description': self.description,
            'quantity': self.quantity,
            'unit_amount': float(self.unit_amount),
            'amount': float(self.amount),
            'currency': self.currency,
            'period_start': self.period_start.isoformat() if self.period_start else None,
            'period_end': self.period_end.isoformat() if self.period_end else None,
            'proration': self.proration,
            'discount_amount': float(self.discount_amount or 0),
            'created_at': self.created_at.isoformat()
        }


class PaymentMethod(db.Model):
    __tablename__ = 'payment_methods'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    stripe_payment_method_id = db.Column(db.String(100), unique=True, nullable=False)
    stripe_customer_id = db.Column(db.String(100))
    
    # Payment method type and details
    type = db.Column(db.String(20), nullable=False)  # card, bank_account, etc.
    
    # Card details (for type='card')
    card_brand = db.Column(db.String(20))  # visa, mastercard, amex, etc.
    card_last4 = db.Column(db.String(4))
    card_exp_month = db.Column(db.Integer)
    card_exp_year = db.Column(db.Integer)
    card_country = db.Column(db.String(2))
    card_funding = db.Column(db.String(10))  # credit, debit, prepaid
    
    # Bank account details (for type='bank_account')
    bank_last4 = db.Column(db.String(4))
    bank_routing_number = db.Column(db.String(20))
    bank_account_type = db.Column(db.String(10))  # checking, savings
    bank_name = db.Column(db.String(100))
    
    # Status and settings
    is_default = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    
    # Billing address
    billing_name = db.Column(db.String(100))
    billing_email = db.Column(db.String(255))
    billing_phone = db.Column(db.String(20))
    billing_address_line1 = db.Column(db.String(200))
    billing_address_line2 = db.Column(db.String(200))
    billing_city = db.Column(db.String(100))
    billing_state = db.Column(db.String(100))
    billing_postal_code = db.Column(db.String(20))
    billing_country = db.Column(db.String(2))
    
    # FIXED: Changed 'metadata' to 'payment_metadata'
    payment_metadata = db.Column(db.Text)  # JSON string
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_used_at = db.Column(db.DateTime)
    
    # Relationships
    user = db.relationship('User', back_populates='payment_methods')
    
    def get_payment_metadata(self):
        """Get payment metadata as a dictionary"""
        if not self.payment_metadata:
            return {}
        try:
            return json.loads(self.payment_metadata)
        except (json.JSONDecodeError, TypeError):
            return {}
    
    def set_payment_metadata(self, metadata_dict):
        """Set payment metadata from a dictionary"""
        if metadata_dict:
            self.payment_metadata = json.dumps(metadata_dict)
        else:
            self.payment_metadata = None
    
    def is_expired(self):
        """Check if card is expired (only for card type)"""
        if self.type != 'card' or not self.card_exp_month or not self.card_exp_year:
            return False
        
        from datetime import date
        today = date.today()
        return (self.card_exp_year < today.year or 
                (self.card_exp_year == today.year and self.card_exp_month < today.month))
    
    def get_display_name(self):
        """Get a user-friendly display name for the payment method"""
        if self.type == 'card':
            brand = self.card_brand.title() if self.card_brand else 'Card'
            return f"{brand} ending in {self.card_last4}"
        elif self.type == 'bank_account':
            account_type = self.bank_account_type.title() if self.bank_account_type else 'Bank'
            bank = self.bank_name or 'Bank'
            return f"{bank} {account_type} ending in {self.bank_last4}"
        else:
            return f"{self.type.title()} Payment Method"
    
    def set_as_default(self):
        """Set this payment method as the default for the user"""
        # Remove default flag from other payment methods
        PaymentMethod.query.filter_by(user_id=self.user_id, is_default=True).update({
            'is_default': False
        })
        
        # Set this one as default
        self.is_default = True
        db.session.commit()
    
    def to_dict(self, include_sensitive=False):
        """Convert to dictionary, optionally including sensitive data"""
        result = {
            'id': self.id,
            'user_id': self.user_id,
            'stripe_payment_method_id': self.stripe_payment_method_id if include_sensitive else None,
            'type': self.type,
            'is_default': self.is_default,
            'is_active': self.is_active,
            'display_name': self.get_display_name(),
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'last_used_at': self.last_used_at.isoformat() if self.last_used_at else None,
            'payment_metadata': self.get_payment_metadata()
        }
        
        # Add type-specific details
        if self.type == 'card':
            result.update({
                'card': {
                    'brand': self.card_brand,
                    'last4': self.card_last4,
                    'exp_month': self.card_exp_month,
                    'exp_year': self.card_exp_year,
                    'country': self.card_country,
                    'funding': self.card_funding,
                    'is_expired': self.is_expired()
                }
            })
        elif self.type == 'bank_account':
            result.update({
                'bank_account': {
                    'last4': self.bank_last4,
                    'routing_number': self.bank_routing_number if include_sensitive else None,
                    'account_type': self.bank_account_type,
                    'bank_name': self.bank_name
                }
            })
        
        return result


# Helper functions

def generate_invoice_number():
    """Generate a unique invoice number"""
    import random
    import string
    
    # Format: INV-YYYYMM-XXXXX
    year_month = datetime.now().strftime('%Y%m')
    random_suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
    
    invoice_number = f"INV-{year_month}-{random_suffix}"
    
    # Ensure uniqueness
    while Invoice.query.filter_by(invoice_number=invoice_number).first():
        random_suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
        invoice_number = f"INV-{year_month}-{random_suffix}"
    
    return invoice_number


def get_user_invoices(user_id, limit=None, status=None):
    """Get invoices for a specific user"""
    query = db.session.query(Invoice).join(Subscription).filter(
        Subscription.user_id == user_id
    )
    
    if status:
        query = query.filter(Invoice.status == status)
    
    query = query.order_by(Invoice.created_at.desc())
    
    if limit:
        query = query.limit(limit)
    
    return query.all()


def get_user_payment_methods(user_id, active_only=True):
    """Get all payment methods for a user"""
    query = PaymentMethod.query.filter_by(user_id=user_id)
    
    if active_only:
        query = query.filter_by(is_active=True)
    
    return query.order_by(PaymentMethod.is_default.desc(), PaymentMethod.created_at.desc()).all()
