
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db
from datetime import datetime

class User(db.Model):
    """User model with proper billing relationships"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    
    # Profile information
    first_name = db.Column(db.String(100))
    last_name = db.Column(db.String(100))
    phone_number = db.Column(db.String(20))
    
    # Account status
    is_active = db.Column(db.Boolean, default=True)
    is_admin = db.Column(db.Boolean, default=False)
    is_verified = db.Column(db.Boolean, default=False)
    
    # Timestamps
    last_login = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships - Use string references to avoid circular imports
    # These will be resolved when the models are loaded
    subscriptions = db.relationship('Subscription', back_populates='user', lazy='dynamic')
    payment_methods = db.relationship('PaymentMethod', back_populates='user', lazy='dynamic')
    payments = db.relationship('Payment', back_populates='user', lazy='dynamic')
    invoices = db.relationship('Invoice', back_populates='user', lazy='dynamic')
    messages = db.relationship('Message', back_populates='user', lazy='dynamic')
    clients = db.relationship('Client', back_populates='user', lazy='dynamic')
    
    # Utility relationships
    activity_logs = db.relationship('ActivityLog', back_populates='user', lazy='dynamic')
    
    def set_password(self, password):
        """Set password hash"""
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        """Check password against hash"""
        return check_password_hash(self.password_hash, password)
    
    @property
    def full_name(self):
        """Get full name"""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.username
    
    def get_active_subscription(self):
        """Get user's active subscription"""
        return self.subscriptions.filter_by(status='active').first()
    
    def get_default_payment_method(self):
        """Get user's default payment method"""
        return self.payment_methods.filter_by(is_default=True, status='active').first()
    
    def to_dict(self, include_relationships=False):
        """Convert user to dictionary"""
        data = {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'phone_number': self.phone_number,
            'full_name': self.full_name,
            'is_active': self.is_active,
            'is_admin': self.is_admin,
            'is_verified': self.is_verified,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
        
        if include_relationships:
            data.update({
                'subscription': self.get_active_subscription().to_dict() if self.get_active_subscription() else None,
                'payment_methods': [pm.to_dict() for pm in self.payment_methods.filter_by(status='active').all()],
                'subscription_count': self.subscriptions.count(),
                'payment_method_count': self.payment_methods.filter_by(status='active').count(),
                'message_count': self.messages.count(),
                'client_count': self.clients.count()
            })
        
        return data
    
    def __repr__(self):
        return f'<User {self.username}>'