"""
Database model for billing settings
"""

from app.extensions import db
from datetime import datetime

class BillingSettings(db.Model):
    """Billing settings model"""
    __tablename__ = 'billing_settings'
    
    id = db.Column(db.String(50), primary_key=True)
    user_id = db.Column(db.String(50), db.ForeignKey('users.id'), nullable=False, unique=True)
    
    # Billing preferences
    auto_pay = db.Column(db.Boolean, default=True)
    billing_email = db.Column(db.String(255))
    billing_address = db.Column(db.JSON)
    
    # Invoice settings
    invoice_delivery = db.Column(db.String(20), default='email')  # email, postal, both
    invoice_format = db.Column(db.String(10), default='pdf')  # pdf, html
    
    # Notification preferences
    notifications = db.Column(db.JSON, default=lambda: {
        'payment_succeeded': True,
        'payment_failed': True,
        'invoice_created': True,
        'subscription_renewed': True,
        'subscription_canceled': True,
        'usage_alerts': True,
        'overage_alerts': True
    })
    
    # Usage alert thresholds (percentages)
    usage_alert_thresholds = db.Column(db.JSON, default=lambda: {
        'sms_credits': 80,
        'ai_credits': 80,
        'storage': 80,
        'api_calls': 80
    })
    
    # Tax information
    tax_id = db.Column(db.String(50))
    tax_exempt = db.Column(db.Boolean, default=False)
    
    # Currency and locale
    currency = db.Column(db.String(3), default='USD')
    locale = db.Column(db.String(10), default='en_US')
    timezone = db.Column(db.String(50), default='UTC')
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Metadata
    metadata = db.Column(db.JSON)
    
    # Relationships
    user = db.relationship('User', backref=db.backref('billing_settings', uselist=False))
    
    @staticmethod
    def create_default(user_id: str):
        """Create default billing settings for a user"""
        user = db.session.get(User, user_id)
        return BillingSettings(
            user_id=user_id,
            billing_email=user.email if user else None,
            auto_pay=True,
            invoice_delivery='email',
            invoice_format='pdf',
            currency='USD',
            locale='en_US',
            timezone='UTC'
        )
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'auto_pay': self.auto_pay,
            'billing_email': self.billing_email,
            'billing_address': self.billing_address,
            'invoice_delivery': self.invoice_delivery,
            'invoice_format': self.invoice_format,
            'notifications': self.notifications,
            'usage_alert_thresholds': self.usage_alert_thresholds,
            'tax_id': self.tax_id,
            'tax_exempt': self.tax_exempt,
            'currency': self.currency,
            'locale': self.locale,
            'timezone': self.timezone,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'metadata': self.metadata
        }
