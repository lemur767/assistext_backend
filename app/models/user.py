
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
    is_trial = db.Column(db.Boolean, default=False)
    trial_status = db.Column(db.String(20), default='inactive')  # active, expired, converted, inactive
    trial_start_date = db.Column(db.DateTime)
    trial_end_date = db.Column(db.DateTime)
    trial_days_remaining = db.Column(db.Integer, default=0)
    trial_expired_at = db.Column(db.DateTime)
    trial_converted_at = db.Column(db.DateTime)
    
    # SignalWire Integration Fields
    signalwire_setup_pending = db.Column(db.Boolean, default=False)
    signalwire_setup_completed = db.Column(db.Boolean, default=False)
    signalwire_subproject_id = db.Column(db.String(50))  # SignalWire subproject SID
    signalwire_auth_token = db.Column(db.String(100))    # Subproject auth token
    signalwire_phone_number = db.Column(db.String(20))   # Assigned phone number
    signalwire_phone_sid = db.Column(db.String(50))      # Phone number SID
    signalwire_number_active = db.Column(db.Boolean, default=False)  # Active/suspended status
    
    # Subscription Fields
    subscription_active = db.Column(db.Boolean, default=False)
    subscription_plan_id = db.Column(db.String(50))
    subscription_activated_at = db.Column(db.DateTime)
    # Account status
    is_active = db.Column(db.Boolean, default=True)
    is_admin = db.Column(db.Boolean, default=False)
    is_verified = db.Column(db.Boolean, default=False)
    
    # Timestamps
    last_login = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    
    subscriptions = db.relationship('Subscription', back_populates='user', lazy='dynamic')
    payment_methods = db.relationship('PaymentMethod', back_populates='user', lazy='dynamic')
    payments = db.relationship('Payment', back_populates='user', lazy='dynamic')
    invoices = db.relationship('Invoice', back_populates='user', lazy='dynamic')
    messages = db.relationship('Message', back_populates='user', lazy='dynamic')
    clients = db.relationship('Client', back_populates='user', lazy='dynamic')
    useage_records = db.relationship('UseageRecord', back_populates='user', lazy='dynamic')
    message_templates = db.relationship('MessageTemplate', back_populates='user', lazy='dynamic')
    credit_transactions = db.relationship('CreditTransaction', back_populates='user', lazy='dynamic')
    
    
    # Utility relationships
    activity_logs = db.relationship('ActivityLog', back_populates='user', lazy='dynamic')
    notification_settings = db.relationship('NotificationSetting', back_populates='user', lazy='dynamic')
    api_keys = db.relationship('APIKey', back_populates='user', lazy='dynamic')
    notification_logs = db.relationship('NotificationLog', back_populates='user', lazy='dynamic')
    
    def get_trial_status(self):
        """Get comprehensive trial status"""
        if not self.is_trial:
            return {
                'is_trial': False,
                'status': 'not_on_trial',
                'subscription_active': self.subscription_active
            }
        
        if self.trial_end_date:
            remaining_time = self.trial_end_date - datetime.utcnow()
            days_remaining = max(0, remaining_time.days)
        else:
            days_remaining = 0
        
        return {
            'is_trial': True,
            'status': self.trial_status,
            'days_remaining': days_remaining,
            'trial_end_date': self.trial_end_date.isoformat() if self.trial_end_date else None,
            'signalwire_active': self.signalwire_number_active,
            'phone_number': self.signalwire_phone_number,
            'can_convert': self.trial_status in ['active', 'expired']
        }
    
    def get_signalwire_status(self):
        """Get SignalWire integration status"""
        return {
            'setup_completed': self.signalwire_setup_completed,
            'phone_number': self.signalwire_phone_number,
            'phone_active': self.signalwire_number_active,
            'subproject_id': self.signalwire_subproject_id,
            'has_phone': bool(self.signalwire_phone_number)
        }

    def set_password(self, password):
        """Set password hash"""
        hash_result = generate_password_hash(password, method='pbkdf2:sha256', salt_length=16)
        
        if isinstance(hash_result, bytes):
            self.password_hash = hash_result.decode('utf-8')
        else:
            self.password_hash = str(hash_result)
        
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
        
        def safe_isoformat(dt):
            if dt is None:
                return None
            if hasattr(dt, 'isoformat'):
                return dt.isoformat()
            return str(dt)
        #Convert user data to a safe JSON Serializable dict
        data = {
            'id': self.id,
            'username': str(self.username) if self.username else None,
            'email': str(self.email) if self.email else None,
            'first_name': str(self.first_name) if self.first_name else None,
            'last_name': str(self.last_name) if self.last_name else None,
            'phone_number': str(self.phone_number) if self.phone_number else None,
            'full_name': str(self.full_name),
            'is_active': bool(self.is_active),
            'is_admin': bool(self.is_admin),
            'is_verified': bool(self.is_verified),
            'last_login': safe_isoformat(self.last_login),
            'created_at': safe_isoformat(self.created_at),
            'updated_at': safe_isoformat(self.updated_at)
        }
        
        if include_relationships:
            try:
                # Get counts safely
                subscription_count = 0
                payment_method_count = 0
                message_count = 0
                client_count = 0
                
                # Only access relationships if user is in session
                if self in db.session:
                    subscription_count = self.subscriptions.count()
                    payment_method_count = self.payment_methods.filter_by(status='active').count() if hasattr(self, 'payment_methods') else 0
                    message_count = self.messages.count()
                    client_count = self.clients.count()
                
                data.update({
                    'subscription_count': int(subscription_count),
                    'payment_method_count': int(payment_method_count),
                    'message_count': int(message_count),
                    'client_count': int(client_count)
                })
                
            except Exception as e:
                # If relationship access fails, just skip it
                data['relationship_error'] = 'Unable to load relationship data'
                
        return data
    
    def to_dict_safe(self):
     
        return {
            'id': self.id,
            'username': str(self.username),
            'email': str(self.email),
            'first_name': str(self.first_name) if self.first_name else '',
            'last_name': str(self.last_name) if self.last_name else '',
            'full_name': str(self.full_name),
            'is_active': bool(self.is_active),
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
     
    def __repr__(self):
        return f'<User {self.username}>'