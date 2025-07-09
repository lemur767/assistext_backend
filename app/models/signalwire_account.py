from app.extensions import db
from datetime import datetime
import json

class SignalWireAccount(db.Model):
    """Tracks SignalWire subaccounts for each subscriber"""
    __tablename__ = 'signalwire_accounts'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    subscription_id = db.Column(db.Integer, db.ForeignKey('subscriptions.id'), nullable=False)
    
    # SignalWire subaccount details
    subaccount_sid = db.Column(db.String(100), unique=True, nullable=False)
    api_token = db.Column(db.String(255), nullable=False)  # Store encrypted
    project_id = db.Column(db.String(100), nullable=False)
    space_url = db.Column(db.String(255), nullable=False)
    
    # Account status
    is_active = db.Column(db.Boolean, default=True)
    monthly_limit = db.Column(db.Integer, default=1000)  # Message limit based on plan
    current_usage = db.Column(db.Integer, default=0)
    
    # Phone numbers allocated to this account
    phone_numbers = db.relationship('SignalWirePhoneNumber', back_populates='account', lazy='dynamic')
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref='signalwire_account')
    subscription = db.relationship('Subscription', backref='signalwire_account')
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'subaccount_sid': self.subaccount_sid,
            'project_id': self.project_id,
            'space_url': self.space_url,
            'is_active': self.is_active,
            'monthly_limit': self.monthly_limit,
            'current_usage': self.current_usage,
            'phone_numbers': [phone.to_dict() for phone in self.phone_numbers],
            'created_at': self.created_at.isoformat()
        }

class SignalWirePhoneNumber(db.Model):
    """Tracks phone numbers assigned to SignalWire accounts"""
    __tablename__ = 'signalwire_phone_numbers'
    
    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey('signalwire_accounts.id'), nullable=False)
    profile_id = db.Column(db.Integer, db.ForeignKey('profiles.id'), nullable=True)
    
    phone_number = db.Column(db.String(20), unique=True, nullable=False)
    friendly_name = db.Column(db.String(100))
    country_code = db.Column(db.String(5), default='CA')  # Canadian numbers
    capabilities = db.Column(db.Text)  # JSON string of SMS/Voice capabilities
    
    # Status tracking
    is_active = db.Column(db.Boolean, default=True)
    is_assigned = db.Column(db.Boolean, default=False)
    monthly_cost = db.Column(db.Numeric(10, 4), default=1.00)  # CAD cost
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    assigned_at = db.Column(db.DateTime)
    
    # Relationships
    account = db.relationship('SignalWireAccount', back_populates='phone_number')
 
    
    def get_capabilities(self):
        if not self.capabilities:
            return {}
        return json.loads(self.capabilities)
    
    def set_capabilities(self, capabilities_dict):
        self.capabilities = json.dumps(capabilities_dict)
    
    def to_dict(self):
        return {
            'id': self.id,
            'phone_number': self.phone_number,
            'friendly_name': self.friendly_name,
            'country_code': self.country_code,
            'capabilities': self.get_capabilities(),
            'is_active': self.is_active,
            'is_assigned': self.is_assigned,
            'monthly_cost': float(self.monthly_cost),
            'created_at': self.created_at.isoformat(),
            'assigned_at': self.assigned_at.isoformat() if self.assigned_at else None
        }