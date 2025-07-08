# app/models/payment.py

from app.extensions import db
from datetime import datetime

class PaymentMethod(db.Model):
    """Payment method model"""
    __tablename__ = 'payment_methods'
    
    id = db.Column(db.String(50), primary_key=True)
    user_id = db.Column(db.String(50), db.ForeignKey('users.id'), nullable=False)
    
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
    
    # Payment processor reference
    processor_id = db.Column(db.String(100))  # Stripe payment method ID
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_used_at = db.Column(db.DateTime)
    
    # Metadata
    metadata = db.Column(db.JSON)
    
    # Relationships
    user = db.relationship('User', backref='payment_methods')
    payments = db.relationship('Payment', backref='payment_method', lazy='dynamic')
    
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
            'metadata': self.metadata
        }


class Payment(db.Model):
    """Payment model"""
    __tablename__ = 'payments'
    
    id = db.Column(db.String(50), primary_key=True)
    user_id = db.Column(db.String(50), db.ForeignKey('users.id'), nullable=False)
    subscription_id = db.Column(db.String(50), db.ForeignKey('subscriptions.id'))
    invoice_id = db.Column(db.String(50), db.ForeignKey('invoices.id'))
    payment_method_id = db.Column(db.String(50), db.ForeignKey('payment_methods.id'))
    
    # Payment details
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    currency = db.Column(db.String(3), default='USD')
    status = db.Column(db.String(20), nullable=False)  # pending, succeeded, failed, canceled, refunded, partially_refunded
    
    # Transaction details
    transaction_id = db.Column(db.String(100))
    processor_response = db.Column(db.JSON)
    
    # Refund information
    refunded_amount = db.Column(db.Numeric(10, 2), default=0.0)
    refund_reason = db.Column(db.Text)
    
    # Payment processor references
    stripe_payment_intent_id = db.Column(db.String(100))
    stripe_invoice_id = db.Column(db.String(100))
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    processed_at = db.Column(db.DateTime)
    
    # Metadata
    description = db.Column(db.Text)
    metadata = db.Column(db.JSON)
    failure_reason = db.Column(db.Text)
    
    # Relationships
    user = db.relationship('User', backref='payments')
    invoice = db.relationship('Invoice', backref='payments')
    
    def to_dict(self, include_relationships=False):
        data = {
            'id': self.id,
            'user_id': self.user_id,
            'subscription_id': self.subscription_id,
            'invoice_id': self.invoice_id,
            'payment_method_id': self.payment_method_id,
            'amount': float(self.amount),
            'currency': self.currency,
            'status': self.status,
            'refunded_amount': float(self.refunded_amount) if self.refunded_amount else 0.0,
            'refund_reason': self.refund_reason,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'processed_at': self.processed_at.isoformat() if self.processed_at else None,
            'description': self.description,
            'failure_reason': self.failure_reason,
            'metadata': self.metadata
        }
        
        if include_relationships:
            data['payment_method'] = self.payment_method.to_dict() if self.payment_method else None
            data['invoice'] = self.invoice.to_dict() if self.invoice else None
        
        return data
