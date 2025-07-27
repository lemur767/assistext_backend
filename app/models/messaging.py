from datetime import datetime
from app.extensions import db


class Client(db.Model):
    """Client/contact management"""
    __tablename__ = 'clients'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Contact Information
    phone_number = db.Column(db.String(20), nullable=False)
    name = db.Column(db.String(100))
    nickname = db.Column(db.String(50))
    email = db.Column(db.String(255))
    display_name = db.Column(db.String(100))
    
    # Location
    city = db.Column(db.String(100))
    state = db.Column(db.String(50))
    country = db.Column(db.String(50))
    timezone = db.Column(db.String(50))
    
    # Relationship Management
    relationship_status = db.Column(db.String(20), default='new')  # new, regular, vip, blocked
    priority_level = db.Column(db.Integer, default=3)  # 1-5 scale
    client_type = db.Column(db.String(50))
    
    # Contact Tracking
    first_contact = db.Column(db.DateTime, default=datetime.utcnow)
    last_interaction = db.Column(db.DateTime, default=datetime.utcnow)
    total_interactions = db.Column(db.Integer, default=0)
    total_messages_received = db.Column(db.Integer, default=0)
    total_messages_sent = db.Column(db.Integer, default=0)
    
    # Client-Specific Settings
    custom_ai_personality = db.Column(db.String(50))
    custom_greeting = db.Column(db.Text)
    auto_reply_enabled = db.Column(db.Boolean, default=True)
    ai_response_style = db.Column(db.String(50))
    
    # Status and Flags
    is_favorite = db.Column(db.Boolean, default=False)
    is_blocked = db.Column(db.Boolean, default=False)
    block_reason = db.Column(db.String(255))
    blocked_at = db.Column(db.DateTime)
    is_flagged = db.Column(db.Boolean, default=False)
    flag_reasons = db.Column(db.JSON)
    
    # Risk Assessment
    risk_level = db.Column(db.String(20), default='low')  # low, medium, high, critical
    trust_score = db.Column(db.Float, default=0.5)
    verified_client = db.Column(db.Boolean, default=False)
    
    # Engagement Metrics
    avg_response_time = db.Column(db.Integer)  # seconds
    last_message_sentiment = db.Column(db.Float)
    engagement_score = db.Column(db.Float, default=0.5)
    
    # Preferences
    preferred_contact_time = db.Column(db.String(20))  # morning, afternoon, evening
    communication_style = db.Column(db.String(50))
    language_preference = db.Column(db.String(10), default='english')
    emoji_preference = db.Column(db.Boolean, default=True)
    
    # Organization
    tags = db.Column(db.JSON)  # Array of tags
    notes = db.Column(db.Text)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', back_populates='clients')
    messages = db.relationship('Message', back_populates='client', lazy='dynamic')
    
    def to_dict(self, include_stats=False):
        data = {
            'id': self.id,
            'user_id': self.user_id,
            'phone_number': self.phone_number,
            'name': self.name,
            'nickname': self.nickname,
            'email': self.email,
            'display_name': self.display_name or self.name or self.phone_number,
            'relationship_status': self.relationship_status,
            'priority_level': self.priority_level,
            'is_favorite': self.is_favorite,
            'is_blocked': self.is_blocked,
            'is_flagged': self.is_flagged,
            'tags': self.tags or [],
            'notes': self.notes,
            'first_contact': self.first_contact.isoformat() if self.first_contact else None,
            'last_interaction': self.last_interaction.isoformat() if self.last_interaction else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
        
        if include_stats:
            data.update({
                'total_interactions': self.total_interactions,
                'total_messages_received': self.total_messages_received,
                'total_messages_sent': self.total_messages_sent,
                'engagement_score': self.engagement_score,
                'trust_score': self.trust_score
            })
        
        return data


class Message(db.Model):
    """SMS message records"""
    __tablename__ = 'messages'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'))
    
    # Message Content
    content = db.Column(db.Text, nullable=False)
    
    # Message Direction
    is_incoming = db.Column(db.Boolean, nullable=False)
    sender_number = db.Column(db.String(20), nullable=False)
    recipient_number = db.Column(db.String(20), nullable=False)
    
    # AI and Processing
    ai_generated = db.Column(db.Boolean, default=False)
    ai_model_used = db.Column(db.String(50))
    processing_time = db.Column(db.Float)  # seconds
    
    # Message Status
    is_read = db.Column(db.Boolean, default=False)
    is_flagged = db.Column(db.Boolean, default=False)
    flag_reasons = db.Column(db.JSON)
    processing_status = db.Column(db.String(20), default='pending')  # pending, delivered, failed, queued
    
    # External Service IDs
    signalwire_sid = db.Column(db.String(100))
    signalwire_status = db.Column(db.String(20))
    
    # Timestamps
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    sent_at = db.Column(db.DateTime)
    delivered_at = db.Column(db.DateTime)
    read_at = db.Column(db.DateTime)
    
    # Analytics
    sentiment_score = db.Column(db.Float)
    intent_category = db.Column(db.String(50))
    
    # Metadata
    message_metadata = db.Column(db.JSON)
    
    # Relationships
    user = db.relationship('User', back_populates='messages')
    client = db.relationship('Client', back_populates='messages')
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'client_id': self.client_id,
            'content': self.content,
            'is_incoming': self.is_incoming,
            'sender_number': self.sender_number,
            'recipient_number': self.recipient_number,
            'ai_generated': self.ai_generated,
            'is_read': self.is_read,
            'is_flagged': self.is_flagged,
            'processing_status': self.processing_status,
            'signalwire_sid': self.signalwire_sid,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'delivered_at': self.delivered_at.isoformat() if self.delivered_at else None
        }


class MessageTemplate(db.Model):
    """Message templates for quick responses"""
    __tablename__ = 'message_templates'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Template Details
    name = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(50))
    
    # Usage
    usage_count = db.Column(db.Integer, default=0)
    last_used_at = db.Column(db.DateTime)
    
    # Status
    is_active = db.Column(db.Boolean, default=True)
    is_default = db.Column(db.Boolean, default=False)
    
    # Variables/Placeholders
    variables = db.Column(db.JSON)  # {name: description} for template variables
    
    # Metadata
    template_metadata = db.Column(db.JSON)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', back_populates='message_templates')
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'content': self.content,
            'description': self.description,
            'category': self.category,
            'usage_count': self.usage_count,
            'is_active': self.is_active,
            'variables': self.variables or {},
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_used_at': self.last_used_at.isoformat() if self.last_used_at else None
        }


class ActivityLog(db.Model):
    """System activity logging"""
    __tablename__ = 'activity_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # Activity Details
    activity_type = db.Column(db.String(50), nullable=False)  # login, message_sent, subscription_created, etc.
    activity_description = db.Column(db.String(255))
    entity_type = db.Column(db.String(50))  # user, client, message, subscription
    entity_id = db.Column(db.Integer)
    
    # Context
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(500))
    session_id = db.Column(db.String(100))
    
    # Result
    success = db.Column(db.Boolean, default=True)
    error_message = db.Column(db.Text)
    
    # Metadata
    activity_metadata = db.Column(db.JSON)
    
    # Timestamp
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', back_populates='activity_logs')
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'activity_type': self.activity_type,
            'activity_description': self.activity_description,
            'entity_type': self.entity_type,
            'entity_id': self.entity_id,
            'success': self.success,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class NotificationLog(db.Model):
    """Notification delivery tracking"""
    __tablename__ = 'notification_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # Notification Details
    notification_type = db.Column(db.String(50), nullable=False)  # email, sms, webhook, in_app
    recipient = db.Column(db.String(255), nullable=False)
    subject = db.Column(db.String(255))
    content = db.Column(db.Text)
    
    # Delivery Status
    status = db.Column(db.String(20), default='pending')  # pending, sent, delivered, failed, bounced
    delivery_attempts = db.Column(db.Integer, default=1)
    
    # External References
    external_id = db.Column(db.String(100))  # Provider message ID
    provider = db.Column(db.String(50))  # sendgrid, twilio, etc.
    
    # Error Handling
    error_message = db.Column(db.Text)
    retry_count = db.Column(db.Integer, default=0)
    next_retry_at = db.Column(db.DateTime)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    sent_at = db.Column(db.DateTime)
    delivered_at = db.Column(db.DateTime)
    
    # Metadata
    notification_metadata = db.Column(db.JSON)
    
    # Relationships
    user = db.relationship('User', back_populates='notification_logs')
    
    def to_dict(self):
        return {
            'id': self.id,
            'notification_type': self.notification_type,
            'recipient': self.recipient,
            'subject': self.subject,
            'status': self.status,
            'delivery_attempts': self.delivery_attempts,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'delivered_at': self.delivered_at.isoformat() if self.delivered_at else None
        }