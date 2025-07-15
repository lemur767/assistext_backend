from app.extensions import db
from datetime import datetime
import json

class ActivityLog(db.Model):
    __tablename__ = 'activity_logs'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'))
    action = db.Column(db.String(100), nullable=False)
    entity_type = db.Column(db.String(50))  # 'profile', 'message', 'client', etc.
    entity_id = db.Column(db.Integer)
    ip_address = db.Column(db.String(45))
    details = db.Column(db.Text)  # JSON data with additional details
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', back_populates='activity_logs')
    
    @property
    def details_dict(self):
        """Return details as dictionary"""
        if self.details:
            return json.loads(self.details)
        return {}
    
    def to_dict(self):
        """Convert activity log to dictionary"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'action': self.action,
            'entity_type': self.entity_type,
            'entity_id': self.entity_id,
            'ip_address': self.ip_address,
            'details': self.details_dict,
            'created_at': self.created_at.isoformat()
        }


class APIKey(db.Model):
    __tablename__ = 'api_keys'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    key_name = db.Column(db.String(100), nullable=False)
    api_key = db.Column(db.String(64), unique=True, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    last_used_at = db.Column(db.DateTime)
    expires_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', back_populates='api_keys')
    
    def update_last_used(self):
        """Update last used timestamp"""
        self.last_used_at = datetime.utcnow()
        db.session.commit()
    
    def is_valid(self):
        """Check if API key is valid and not expired"""
        if not self.is_active:
            return False
        
        if self.expires_at and self.expires_at < datetime.utcnow():
            return False
        
        return True
    
    def to_dict(self):
        """Convert API key to dictionary (without actual key)"""
        return {
            'id': self.id,
            'key_name': self.key_name,
            'is_active': self.is_active,
            'last_used_at': self.last_used_at.isoformat() if self.last_used_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }


class NotificationSetting(db.Model):
    __tablename__ = 'notification_settings'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    notification_type = db.Column(db.String(50), nullable=False)  # 'email', 'sms', 'push'
    event_type = db.Column(db.String(50), nullable=False)  # 'new_message', 'flagged_message', 'subscription'
    is_enabled = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Enforce unique constraint on user_id, notification_type, and event_type
    __table_args__ = (
        db.UniqueConstraint('user_id', 'notification_type', 'event_type'),
    )
    
    # Relationships
    user = db.relationship('User', back_populates='notification_settings')
    
    @classmethod
    def is_enabled(cls, user_id, notification_type, event_type):
        """Check if notification is enabled"""
        setting = cls.query.filter_by(
            user_id=user_id,
            notification_type=notification_type,
            event_type=event_type
        ).first()
        
        # Default to enabled if setting doesn't exist
        if not setting:
            return True
        
        return setting.is_enabled
    
    def to_dict(self):
        """Convert notification setting to dictionary"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'notification_type': self.notification_type,
            'event_type': self.event_type,
            'is_enabled': self.is_enabled,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }


class NotificationLog(db.Model):
    __tablename__ = 'notification_logs'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    notification_type = db.Column(db.String(50), nullable=False)
    event_type = db.Column(db.String(50), nullable=False)
    content = db.Column(db.Text)
    status = db.Column(db.String(20))  # 'sent', 'delivered', 'failed'
    error_message = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', back_populates='notification_logs')
    
    @classmethod
    def log_notification(cls, user_id, notification_type, event_type, content=None, status='sent', error=None):
        """Log a notification"""
        log = cls(
            user_id=user_id,
            notification_type=notification_type,
            event_type=event_type,
            content=content,
            status=status,
            error_message=error
        )
        
        db.session.add(log)
        db.session.commit()
        
        return log
    
    def to_dict(self):
        """Convert notification log to dictionary"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'notification_type': self.notification_type,
            'event_type': self.event_type,
            'content': self.content,
            'status': self.status,
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat()
        }
class MessageTemplate(db.Model):
    __tablename__ = 'message_templates'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # ✅ FIXED: Proper foreign key reference
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    name = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50))  # greeting, info, pricing, etc.
    is_active = db.Column(db.Boolean, default=True)
    usage_count = db.Column(db.Integer, default=0)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # ✅ FIXED: Proper back_populates reference
    user = db.relationship('User', back_populates='message_templates')
    
    def increment_usage(self):
        """Increment usage count"""
        self.usage_count += 1
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'name': self.name,
            'content': self.content,
            'category': self.category,
            'is_active': self.is_active,
            'usage_count': self.usage_count,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
