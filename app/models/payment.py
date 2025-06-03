from app.extensions import db
from datetime import datetime

# app/models/payment_method.py
from app.extensions import db
from datetime import datetime
import json


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
    
    # Metadata and tracking
    paymentMethod = db.Column(db.Text)  # JSON string
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_used_at = db.Column(db.DateTime)
    
    # Relationships
    user = db.relationship('User', back_populates='payment_methods')
    
    def get_metadata(self):
        """Get payment_method.metadata as a dictionary"""
        if not self.payment_method.metadata:
            return {}
        return json.loads(self.payment_method.metadata)
    
    def set_metadata(self, metadata_dict):
        """Set payment_method.metadata from a dictionary"""
        self.payment_method.metadata = json.dumps(metadata_dict)
    
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
    
    def get_expiry_string(self):
        """Get expiry date as MM/YY string (for cards)"""
        if self.type == 'card' and self.card_exp_month and self.card_exp_year:
            return f"{self.card_exp_month:02d}/{str(self.card_exp_year)[-2:]}"
        return None
    
    def set_as_default(self):
        """Set this payment method as the default for the user"""
        # Remove default flag from other payment methods
        PaymentMethod.query.filter_by(user_id=self.user_id, is_default=True).update({
            'is_default': False
        })
        
        # Set this one as default
        self.is_default = True
        db.session.commit()
    
    def deactivate(self):
        """Deactivate this payment method"""
        self.is_active = False
        self.is_default = False
        db.session.commit()
    
    def update_last_used(self):
        """Update the last used timestamp"""
        self.last_used_at = datetime.utcnow()
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
            'payment_method.metadata': self.get_metadata()
        }
        
        # Add type-specific details
        if self.type == 'card':
            result.update({
                'card': {
                    'brand': self.card_brand,
                    'last4': self.card_last4,
                    'exp_month': self.card_exp_month,
                    'exp_year': self.card_exp_year,
                    'expiry_string': self.get_expiry_string(),
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
        
        # Add billing address if present
        if self.billing_address_line1:
            result['billing_address'] = {
                'name': self.billing_name,
                'email': self.billing_email,
                'phone': self.billing_phone,
                'line1': self.billing_address_line1,
                'line2': self.billing_address_line2,
                'city': self.billing_city,
                'state': self.billing_state,
                'postal_code': self.billing_postal_code,
                'country': self.billing_country
            }
        
        return result


# Helper functions for payment method management

def create_payment_method_from_stripe(user_id, stripe_payment_method):
    """Create payment method from Stripe payment method object"""
    
    payment_method = PaymentMethod(
        user_id=user_id,
        stripe_payment_method_id=stripe_payment_method.id,
        stripe_customer_id=stripe_payment_method.customer,
        type=stripe_payment_method.type
    )
    
    # Handle card details
    if stripe_payment_method.type == 'card' and stripe_payment_method.card:
        card = stripe_payment_method.card
        payment_method.card_brand = card.brand
        payment_method.card_last4 = card.last4
        payment_method.card_exp_month = card.exp_month
        payment_method.card_exp_year = card.exp_year
        payment_method.card_country = card.country
        payment_method.card_funding = card.funding
    
    # Handle bank account details
    elif stripe_payment_method.type == 'us_bank_account' and stripe_payment_method.us_bank_account:
        bank = stripe_payment_method.us_bank_account
        payment_method.bank_last4 = bank.last4
        payment_method.bank_routing_number = bank.routing_number
        payment_method.bank_account_type = bank.account_type
        payment_method.bank_name = bank.bank_name
    
    # Handle billing details
    if stripe_payment_method.billing_details:
        billing = stripe_payment_method.billing_details
        payment_method.billing_name = billing.name
        payment_method.billing_email = billing.email
        payment_method.billing_phone = billing.phone
        
        if billing.address:
            payment_method.billing_address_line1 = billing.address.line1
            payment_method.billing_address_line2 = billing.address.line2
            payment_method.billing_city = billing.address.city
            payment_method.billing_state = billing.address.state
            payment_method.billing_postal_code = billing.address.postal_code
            payment_method.billing_country = billing.address.country
    
    db.session.add(payment_method)
    db.session.commit()
    
    return payment_method


def get_user_default_payment_method(user_id):
    """Get the user's default payment method"""
    return PaymentMethod.query.filter_by(
        user_id=user_id,
        is_default=True,
        is_active=True
    ).first()


def get_user_payment_methods(user_id, active_only=True):
    """Get all payment methods for a user"""
    query = PaymentMethod.query.filter_by(user_id=user_id)
    
    if active_only:
        query = query.filter_by(is_active=True)
    
    return query.order_by(PaymentMethod.is_default.desc(), PaymentMethod.created_at.desc()).all()


def cleanup_expired_payment_methods():
    """Deactivate expired payment methods"""
    from datetime import date
    today = date.today()
    
    expired_cards = PaymentMethod.query.filter(
        PaymentMethod.type == 'card',
        PaymentMethod.is_active == True,
        db.or_(
            PaymentMethod.card_exp_year < today.year,
            db.and_(
                PaymentMethod.card_exp_year == today.year,
                PaymentMethod.card_exp_month < today.month
            )
        )
    ).all()
    
    for payment_method in expired_cards:
        payment_method.deactivate()
    
    return len(expired_cards)