from app.extensions import db
from datetime import datetime, timedelta
import json

class SubscriptionPlan(db.Model):
    __tablename__ = 'subscription_plans'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    billing_cycle = db.Column(db.String(20), default='monthly')  # 'monthly' or 'yearly'
    
    # Feature limits
    max_profiles = db.Column(db.Integer, default=1)
    monthly_message_limit = db.Column(db.Integer)  # NULL = unlimited
    monthly_ai_response_limit = db.Column(db.Integer)  # NULL = unlimited
    message_history_days = db.Column(db.Integer, default=30)
    
    # Stripe integration
    stripe_product_id = db.Column(db.String(100))
    stripe_price_id = db.Column(db.String(100))
    
    # Features and metadata
    features = db.Column(db.Text)  # JSON string of features
    is_active = db.Column(db.Boolean, default=True)
    is_featured = db.Column(db.Boolean, default=False)
    sort_order = db.Column(db.Integer, default=0)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    subscriptions = db.relationship('Subscription', back_populates='plan')
    
    def get_features(self):
        """Return features as dictionary"""
        if self.features:
            return json.loads(self.features)
        return {}
    
    def set_features(self, features_dict):
        """Set features from dictionary"""
        self.features = json.dumps(features_dict)
    
    def to_dict(self):
        """Convert plan to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'price': float(self.price),
            'billing_cycle': self.billing_cycle,
            'max_profiles': self.max_profiles,
            'monthly_message_limit': self.monthly_message_limit,
            'monthly_ai_response_limit': self.monthly_ai_response_limit,
            'message_history_days': self.message_history_days,
            'features': self.get_features(),
            'is_active': self.is_active,
            'is_featured': self.is_featured,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }


class Subscription(db.Model):
    __tablename__ = 'subscriptions'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    plan_id = db.Column(db.Integer, db.ForeignKey('subscription_plans.id'), nullable=False)
    stripe_subscription_id = db.Column(db.String(100))
    stripe_customer_id = db.Column(db.String(100))
    payment_method_id = db.Column(db.Integer, db.ForeignKey('payment_methods.id'))
    
    start_date = db.Column(db.DateTime, default=datetime.utcnow)
    end_date = db.Column(db.DateTime)
    renewal_date = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True)
    payment_status = db.Column(db.String(20), default='active')  # active, past_due, failed, canceled
    
    auto_renew = db.Column(db.Boolean, default=True)
    subscription_metadata = db.Column(db.Text)  # JSON field for additional data
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', back_populates='subscriptions')
    plan = db.relationship('SubscriptionPlan', back_populates='subscriptions')
    payment_method = db.relationship('PaymentMethod', foreign_keys=[payment_method_id])
    invoices = db.relationship('Invoice', back_populates='subscription', lazy='dynamic')
    
    def set_metadata(self, metadata_dict):
        self.subscription_metadata = json.dumps(metadata_dict)
    
    def get_metadata(self):
        if not self.subscription_metadata:
            return {}
        return json.loads(self.subscription_metadata)
    
    def get_current_period_start(self):
        """Get the start date of the current billing period"""
        if self.renewal_date:
            if self.plan.billing_cycle == 'monthly':
                return self.renewal_date - timedelta(days=30)
            elif self.plan.billing_cycle == 'yearly':
                return self.renewal_date - timedelta(days=365)
        return self.start_date
    
    def get_current_period_end(self):
        """Get the end date of the current billing period"""
        if self.renewal_date:
            return self.renewal_date
        
        if self.plan.billing_cycle == 'monthly':
            return self.start_date + timedelta(days=30)
        elif self.plan.billing_cycle == 'yearly':
            return self.start_date + timedelta(days=365)
        else:
            return self.start_date + timedelta(days=30)
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'plan_id': self.plan_id,
            'plan': self.plan.to_dict() if self.plan else None,
            'stripe_subscription_id': self.stripe_subscription_id,
            'stripe_customer_id': self.stripe_customer_id,
            'payment_method_id': self.payment_method_id,
            'payment_method': self.payment_method.to_dict() if self.payment_method else None,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'renewal_date': self.renewal_date.isoformat() if self.renewal_date else None,
            'is_active': self.is_active,
            'payment_status': self.payment_status,
            'auto_renew': self.auto_renew,
            'subscription_metadata': self.get_metadata(),
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'current_period': {
                'start': self.get_current_period_start().isoformat(),
                'end': self.get_current_period_end().isoformat()
            }
        }


class Invoice(db.Model):
    __tablename__ = 'invoices'
    __table_args__ = {'extend_existing': True}
    
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
    
    # Metadata for additional info
    invoice_metadata = db.Column(db.Text)  # JSON string for flexible data storage
    
    # Relationships
    subscription = db.relationship('Subscription', back_populates='invoices')
    invoice_items = db.relationship('InvoiceItem', back_populates='invoice', cascade='all, delete-orphan')
    
    def get_metadata(self):
        """Get metadata as a dictionary"""
        if not self.invoice_metadata:
            return {}
        return json.loads(self.invoice_metadata)
    
    def set_metadata(self, metadata_dict):
        """Set metadata from a dictionary"""
        self.invoice_metadata = json.dumps(metadata_dict)
    
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
            'invoice_metadata': self.get_metadata(),
            'balance_due': self.get_balance_due(),
            'is_paid': self.is_paid(),
            'is_overdue': self.is_overdue()
        }


class InvoiceItem(db.Model):
    __tablename__ = 'invoice_items'
    __table_args__ = {'extend_existing': True}
    
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