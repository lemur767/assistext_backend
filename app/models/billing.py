from datetime import datetime
from app.extensions import db


class SubscriptionPlan(db.Model):
    """Subscription plan definitions"""
    __tablename__ = 'subscription_plans'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    status = db.Column(db.String(20), default='active')  # active, inactive, archived
    
    # Pricing
    monthly_price = db.Column(db.Numeric(10, 2), nullable=False)
    annual_price = db.Column(db.Numeric(10, 2), nullable=False)
    currency = db.Column(db.String(3), default='USD')
    setup_fee = db.Column(db.Numeric(10, 2), default=0.0)
    
    # Trial
    trial_period_days = db.Column(db.Integer, default=0)
    
    # Features (stored as JSON)
    features = db.Column(db.JSON, nullable=False)
    
    # Marketing
    popular = db.Column(db.Boolean, default=False)
    recommended = db.Column(db.Boolean, default=False)
    category = db.Column(db.String(50))
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Metadata
    sub_plan_metadata = db.Column(db.JSON)
    
    # Relationships
    subscriptions = db.relationship('Subscription', back_populates='plan', lazy='dynamic')
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'status': self.status,
            'monthly_price': float(self.monthly_price),
            'annual_price': float(self.annual_price),
            'currency': self.currency,
            'setup_fee': float(self.setup_fee) if self.setup_fee else 0.0,
            'trial_period_days': self.trial_period_days,
            'features': self.features,
            'popular': self.popular,
            'recommended': self.recommended,
            'category': self.category,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'sub_plan_metadata': self.sub_plan_metadata
        }


class Subscription(db.Model):
    """User subscription model"""
    __tablename__ = 'subscriptions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    plan_id = db.Column(db.Integer, db.ForeignKey('subscription_plans.id'), nullable=False)
    
    # Status
    status = db.Column(db.String(20), nullable=False)  # active, canceled, past_due, unpaid, paused, trialing, incomplete
    
    # Billing
    billing_cycle = db.Column(db.String(10), nullable=False)  # monthly, annual
    auto_renew = db.Column(db.Boolean, default=True)
    
    # Dates
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    current_period_start = db.Column(db.DateTime, nullable=False)
    current_period_end = db.Column(db.DateTime, nullable=False)
    trial_start = db.Column(db.DateTime)
    trial_end = db.Column(db.DateTime)
    canceled_at = db.Column(db.DateTime)
    
    # Financial
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    currency = db.Column(db.String(3), default='USD')
    discount_amount = db.Column(db.Numeric(10, 2), default=0.0)
    tax_amount = db.Column(db.Numeric(10, 2), default=0.0)
    
    # External references
    stripe_subscription_id = db.Column(db.String(100), unique=True)
    stripe_customer_id = db.Column(db.String(100))
    
    # Metadata
    script_metadata = db.Column(db.JSON)
    cancellation_reason = db.Column(db.String(255))
    
    # Relationships
    user = db.relationship('User', back_populates='subscriptions')
    plan = db.relationship('SubscriptionPlan', back_populates='subscriptions')
    invoices = db.relationship('Invoice', back_populates='subscription', lazy='dynamic')
    usage_records = db.relationship('UsageRecord', back_populates='subscription', lazy='dynamic')
    payments = db.relationship('Payment', back_populates='subscription', lazy='dynamic')
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'plan_id': self.plan_id,
            'status': self.status,
            'billing_cycle': self.billing_cycle,
            'auto_renew': self.auto_renew,
            'amount': float(self.amount),
            'currency': self.currency,
            'current_period_start': self.current_period_start.isoformat() if self.current_period_start else None,
            'current_period_end': self.current_period_end.isoformat() if self.current_period_end else None,
            'trial_start': self.trial_start.isoformat() if self.trial_start else None,
            'trial_end': self.trial_end.isoformat() if self.trial_end else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'plan': self.plan.to_dict() if self.plan else None
        }


class Invoice(db.Model):
    """Billing invoices"""
    __tablename__ = 'invoices'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    subscription_id = db.Column(db.Integer, db.ForeignKey('subscriptions.id'))
    
    # Invoice details
    invoice_number = db.Column(db.String(50), unique=True, nullable=False)
    status = db.Column(db.String(20), nullable=False)  # draft, pending, paid, failed, canceled
    
    # Financial
    subtotal = db.Column(db.Numeric(10, 2), nullable=False)
    tax_amount = db.Column(db.Numeric(10, 2), default=0.0)
    discount_amount = db.Column(db.Numeric(10, 2), default=0.0)
    total_amount = db.Column(db.Numeric(10, 2), nullable=False)
    amount_paid = db.Column(db.Numeric(10, 2), default=0.0)
    amount_due = db.Column(db.Numeric(10, 2), nullable=False)
    currency = db.Column(db.String(3), default='USD')
    
    # Dates
    invoice_date = db.Column(db.DateTime, default=datetime.utcnow)
    due_date = db.Column(db.DateTime, nullable=False)
    paid_at = db.Column(db.DateTime)
    
    # External references
    stripe_invoice_id = db.Column(db.String(100), unique=True)
    
    # Metadata
    notes = db.Column(db.Text)
    invoice_metadata = db.Column(db.JSON)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', back_populates='invoices')
    subscription = db.relationship('Subscription', back_populates='invoices')
    items = db.relationship('InvoiceItem', back_populates='invoice', lazy='dynamic')
    payments = db.relationship('Payment', back_populates='invoice', lazy='dynamic')
    
    def to_dict(self):
        return {
            'id': self.id,
            'invoice_number': self.invoice_number,
            'status': self.status,
            'subtotal': float(self.subtotal),
            'tax_amount': float(self.tax_amount),
            'total_amount': float(self.total_amount),
            'amount_paid': float(self.amount_paid),
            'amount_due': float(self.amount_due),
            'currency': self.currency,
            'invoice_date': self.invoice_date.isoformat() if self.invoice_date else None,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'paid_at': self.paid_at.isoformat() if self.paid_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class InvoiceItem(db.Model):
    """Invoice line items"""
    __tablename__ = 'invoice_items'
    
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'), nullable=False)
    
    # Item details
    description = db.Column(db.String(255), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)
    total_price = db.Column(db.Numeric(10, 2), nullable=False)
    
    # Metadata
    item_type = db.Column(db.String(50))  # subscription, usage, one_time, etc.
    period_start = db.Column(db.DateTime)
    period_end = db.Column(db.DateTime)
    item_metadata = db.Column(db.JSON)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    invoice = db.relationship('Invoice', back_populates='items')
    
    def to_dict(self):
        return {
            'id': self.id,
            'description': self.description,
            'quantity': self.quantity,
            'unit_price': float(self.unit_price),
            'total_price': float(self.total_price),
            'item_type': self.item_type
        }


class PaymentMethod(db.Model):
    """User payment methods"""
    __tablename__ = 'payment_methods'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Payment method details
    type = db.Column(db.String(20), nullable=False)  # card, bank, paypal, etc.
    is_default = db.Column(db.Boolean, default=False)
    
    # Card details (for display only - no sensitive data)
    card_brand = db.Column(db.String(20))  # visa, mastercard, etc.
    card_last4 = db.Column(db.String(4))
    card_exp_month = db.Column(db.Integer)
    card_exp_year = db.Column(db.Integer)
    
    # Status
    status = db.Column(db.String(20), default='active')  # active, expired, invalid
    
    # External references
    stripe_payment_method_id = db.Column(db.String(100), unique=True)
    
    # Metadata
    pm_metadata = db.Column(db.JSON)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_used_at = db.Column(db.DateTime)
    
    # Relationships
    user = db.relationship('User', back_populates='payment_methods')
    payments = db.relationship('Payment', back_populates='payment_method', lazy='dynamic')
    
    def to_dict(self):
        return {
            'id': self.id,
            'type': self.type,
            'is_default': self.is_default,
            'card_brand': self.card_brand,
            'card_last4': self.card_last4,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Payment(db.Model):
    """Payment records"""
    __tablename__ = 'payments'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    subscription_id = db.Column(db.Integer, db.ForeignKey('subscriptions.id'))
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'))
    payment_method_id = db.Column(db.Integer, db.ForeignKey('payment_methods.id'))
    
    # Payment details
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    currency = db.Column(db.String(3), default='USD')
    status = db.Column(db.String(20), nullable=False)  # pending, succeeded, failed, canceled, refunded
    
    # Transaction details
    transaction_id = db.Column(db.String(100))
    processor_response = db.Column(db.JSON)
    failure_reason = db.Column(db.String(255))
    
    # Refund information
    refunded_amount = db.Column(db.Numeric(10, 2), default=0.0)
    refund_reason = db.Column(db.Text)
    
    # External references
    stripe_payment_intent_id = db.Column(db.String(100), unique=True)
    stripe_invoice_id = db.Column(db.String(100))
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    processed_at = db.Column(db.DateTime)
    
    # Metadata
    pay_metadata = db.Column(db.JSON)
    
    # Relationships
    user = db.relationship('User', back_populates='payments')
    subscription = db.relationship('Subscription', back_populates='payments')
    invoice = db.relationship('Invoice', back_populates='payments')
    payment_method = db.relationship('PaymentMethod', back_populates='payments')
    
    def to_dict(self):
        return {
            'id': self.id,
            'amount': float(self.amount),
            'currency': self.currency,
            'status': self.status,
            'processed_at': self.processed_at.isoformat() if self.processed_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class UsageRecord(db.Model):
    """Usage tracking for billing"""
    __tablename__ = 'usage_records'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    subscription_id = db.Column(db.Integer, db.ForeignKey('subscriptions.id'))
    
    # Usage details
    resource_type = db.Column(db.String(50), nullable=False)  # sms, ai_response, storage, etc.
    quantity = db.Column(db.Integer, nullable=False, default=1)
    unit_cost = db.Column(db.Numeric(10, 4), default=0.0)
    total_cost = db.Column(db.Numeric(10, 2), default=0.0)
    
    # Period
    period_start = db.Column(db.DateTime, nullable=False)
    period_end = db.Column(db.DateTime, nullable=False)
    
    # Metadata
    usage_metadata = db.Column(db.JSON)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', back_populates='usage_records')
    subscription = db.relationship('Subscription', back_populates='usage_records')
    
    def to_dict(self):
        return {
            'id': self.id,
            'resource_type': self.resource_type,
            'quantity': self.quantity,
            'period_start': self.period_start.isoformat() if self.period_start else None,
            'period_end': self.period_end.isoformat() if self.period_end else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }