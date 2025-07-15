
from app.extensions import db
from datetime import datetime

class PaymentMethod(db.Model):
    """
    SINGLE PaymentMethod model - consolidated from multiple files
    """
    __tablename__ = 'payment_methods'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Payment method details
    type = db.Column(db.String(20), nullable=False)  # card, bank, paypal, etc.
    is_default = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(20), default='active')  # active, expired, invalid
    
    # Card details (for display only - no sensitive data)
    card_brand = db.Column(db.String(20))
    card_last4 = db.Column(db.String(4))
    card_exp_month = db.Column(db.Integer)
    card_exp_year = db.Column(db.Integer)
    
    # Bank details (for display only)
    bank_name = db.Column(db.String(100))
    bank_last4 = db.Column(db.String(4))
    
    # Billing address
    billing_address = db.Column(db.JSON)
    
    # Payment processor references
    stripe_payment_method_id = db.Column(db.String(100), unique=True)
    stripe_customer_id = db.Column(db.String(100))
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_used_at = db.Column(db.DateTime)
    
    # Metadata
    pm_metadata = db.Column(db.JSON)
    
    # Relationships
    user = db.relationship('User', back_populates='payment_methods')
    payments = db.relationship('Payment', back_populates='payment_method', lazy='dynamic')
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'type': self.type,
            'is_default': self.is_default,
            'status': self.status,
            'card_brand': self.card_brand,
            'card_last4': self.card_last4,
            'card_exp_month': self.card_exp_month,
            'card_exp_year': self.card_exp_year,
            'bank_name': self.bank_name,
            'bank_last4': self.bank_last4,
            'billing_address': self.billing_address,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'last_used_at': self.last_used_at.isoformat() if self.last_used_at else None,
            'pm_metadata': self.pm_metadata
        }


class Payment(db.Model):
    """Payment model"""
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
    
    # Refund information
    refunded_amount = db.Column(db.Numeric(10, 2), default=0.0)
    refund_reason = db.Column(db.Text)
    
    # Payment processor references
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
            'user_id': self.user_id,
            'subscription_id': self.subscription_id,
            'invoice_id': self.invoice_id,
            'payment_method_id': self.payment_method_id,
            'amount': float(self.amount),
            'currency': self.currency,
            'status': self.status,
            'transaction_id': self.transaction_id,
            'refunded_amount': float(self.refunded_amount or 0),
            'refund_reason': self.refund_reason,
            'stripe_payment_intent_id': self.stripe_payment_intent_id,
            'stripe_invoice_id': self.stripe_invoice_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'processed_at': self.processed_at.isoformat() if self.processed_at else None,
            'pay_metadata': self.pay_metadata
        }


class Invoice(db.Model):
    """Invoice model"""
    __tablename__ = 'invoices'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    subscription_id = db.Column(db.Integer, db.ForeignKey('subscriptions.id'))
    
    # Invoice details
    invoice_number = db.Column(db.String(50), unique=True, nullable=False)
    status = db.Column(db.String(20), nullable=False)  # draft, open, paid, void, uncollectible
    
    # Amount details
    subtotal = db.Column(db.Numeric(10, 2), nullable=False)
    tax_amount = db.Column(db.Numeric(10, 2), default=0.0)
    discount_amount = db.Column(db.Numeric(10, 2), default=0.0)
    total = db.Column(db.Numeric(10, 2), nullable=False)
    currency = db.Column(db.String(3), default='USD')
    
    # Payment details
    amount_paid = db.Column(db.Numeric(10, 2), default=0.0)
    amount_due = db.Column(db.Numeric(10, 2), nullable=False)
    
    # Billing period
    period_start = db.Column(db.DateTime)
    period_end = db.Column(db.DateTime)
    
    # Due date
    due_date = db.Column(db.DateTime)
    
    # Stripe references
    stripe_invoice_id = db.Column(db.String(100), unique=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    paid_at = db.Column(db.DateTime)
    
    # Metadata
    inv_metadata = db.Column(db.JSON)
    
    # Relationships
    user = db.relationship('User', back_populates='invoices')
    subscription = db.relationship('Subscription', back_populates='invoices')
    invoice_items = db.relationship('InvoiceItem', back_populates='invoice', lazy='dynamic')
    payments = db.relationship('Payment', back_populates='invoice', lazy='dynamic')
    
    def to_dict(self, include_items=False):
        data = {
            'id': self.id,
            'user_id': self.user_id,
            'subscription_id': self.subscription_id,
            'invoice_number': self.invoice_number,
            'status': self.status,
            'subtotal': float(self.subtotal),
            'tax_amount': float(self.tax_amount or 0),
            'discount_amount': float(self.discount_amount or 0),
            'total': float(self.total),
            'currency': self.currency,
            'amount_paid': float(self.amount_paid or 0),
            'amount_due': float(self.amount_due),
            'period_start': self.period_start.isoformat() if self.period_start else None,
            'period_end': self.period_end.isoformat() if self.period_end else None,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'stripe_invoice_id': self.stripe_invoice_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'paid_at': self.paid_at.isoformat() if self.paid_at else None,
            'inv_metadata': self.inv_metadata
        }
        
        if include_items:
            data['items'] = [item.to_dict() for item in self.invoice_items]
            
        return data


class InvoiceItem(db.Model):
    """Invoice item model"""
    __tablename__ = 'invoice_items'
    
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'), nullable=False)
    
    # Item details
    description = db.Column(db.String(255), nullable=False)
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
    
    # Stripe reference
    stripe_invoice_item_id = db.Column(db.String(100))
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Metadata
    inv_item_metadata = db.Column(db.JSON)
    
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
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'inv_item_metadata': self.inv_item_metadata
        }