# app/models/subscription.py
"""
Database models for subscriptions and subscription plans
"""

from app.extensions import db
from datetime import datetime
import json

class SubscriptionPlan(db.Model):
    """Subscription plan model"""
    __tablename__ = 'subscription_plans'
    
    id = db.Column(db.String(50), primary_key=True)
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
    metadata = db.Column(db.JSON)
    
    # Relationships
    subscriptions = db.relationship('Subscription', backref='plan', lazy='dynamic')
    
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
            'metadata': self.metadata
        }


class Subscription(db.Model):
    """User subscription model"""
    __tablename__ = 'subscriptions'
    
    id = db.Column(db.String(50), primary_key=True)
    user_id = db.Column(db.String(50), db.ForeignKey('users.id'), nullable=False)
    plan_id = db.Column(db.String(50), db.ForeignKey('subscription_plans.id'), nullable=False)
    
    # Status
    status = db.Column(db.String(20), nullable=False)  # active, canceled, past_due, unpaid, paused, trialing, incomplete
    
    # Billing
    billing_cycle = db.Column(db.String(10), nullable=False)  # monthly, annual
    auto_renew = db.Column(db.Boolean, default=True)
    
    # Dates
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    current_period_start = db.Column(db.DateTime)
    current_period_end = db.Column(db.DateTime)
    trial_end = db.Column(db.DateTime)
    canceled_at = db.Column(db.DateTime)
    pause_until = db.Column(db.DateTime)
    
    # Financial
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    currency = db.Column(db.String(3), default='USD')
    discount_amount = db.Column(db.Numeric(10, 2), default=0.0)
    tax_amount = db.Column(db.Numeric(10, 2), default=0.0)
    
    # Cancellation
    cancel_at_period_end = db.Column(db.Boolean, default=False)
    cancellation_reason = db.Column(db.Text)
    pause_reason = db.Column(db.Text)
    
    # Payment processor IDs
    stripe_subscription_id = db.Column(db.String(100))
    stripe_customer_id = db.Column(db.String(100))
    
    # Metadata
    metadata = db.Column(db.JSON)
    
    # Relationships
    user = db.relationship('User', backref='subscriptions')
    payments = db.relationship('Payment', backref='subscription', lazy='dynamic')
    invoices = db.relationship('Invoice', backref='subscription', lazy='dynamic')
    usage_records = db.relationship('Usage', backref='subscription', lazy='dynamic')
    
    def to_dict(self, include_relationships=False):
        data = {
            'id': self.id,
            'user_id': self.user_id,
            'plan_id': self.plan_id,
            'status': self.status,
            'billing_cycle': self.billing_cycle,
            'auto_renew': self.auto_renew,
            'amount': float(self.amount),
            'currency': self.currency,
            'discount_amount': float(self.discount_amount) if self.discount_amount else 0.0,
            'tax_amount': float(self.tax_amount) if self.tax_amount else 0.0,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'current_period_start': self.current_period_start.isoformat() if self.current_period_start else None,
            'current_period_end': self.current_period_end.isoformat() if self.current_period_end else None,
            'trial_end': self.trial_end.isoformat() if self.trial_end else None,
            'canceled_at': self.canceled_at.isoformat() if self.canceled_at else None,
            'pause_until': self.pause_until.isoformat() if self.pause_until else None,
            'cancel_at_period_end': self.cancel_at_period_end,
            'cancellation_reason': self.cancellation_reason,
            'stripe_subscription_id': self.stripe_subscription_id,
            'metadata': self.metadata
        }
        
        if include_relationships:
            data['plan'] = self.plan.to_dict() if self.plan else None
            data['latest_invoice'] = self.invoices.order_by(db.desc(Invoice.created_at)).first().to_dict() if self.invoices.first() else None
        
        return data