from app.extensions import db
from datetime import datetime
from typing import Dict, Any, Optional

class Message(db.Model):
    __tablename__ = 'messages'
    
    id = db.Column(db.Integer, primary_key=True)
    message_sid = db.Column(db.String(34), unique=True, nullable=True, index=True)  # SignalWire message ID
    
    # UPDATED: Changed from profile_id to user_id
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True, index=True)
    
    # Message content
    message_body = db.Column(db.Text, nullable=False)
    sender_number = db.Column(db.String(20), nullable=False, index=True)
    recipient_number = db.Column(db.String(20), nullable=False, index=True)
    
    # Message metadata
    direction = db.Column(db.String(10), nullable=False)  # 'inbound' or 'outbound'
    status = db.Column(db.String(20), default='sent')  # 'sent', 'delivered', 'failed', etc.
    is_ai_generated = db.Column(db.Boolean, default=False)
    is_read = db.Column(db.Boolean, default=False)
    is_flagged = db.Column(db.Boolean, default=False)
    
    # Threading and responses
    related_message_sid = db.Column(db.String(34), nullable=True)  # For threading responses
    
    # Error handling
    error_message = db.Column(db.Text, nullable=True)
    retry_count = db.Column(db.Integer, default=0)
    
    # Timestamps
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships (UPDATED)
    user = db.relationship('User', back_populates='messages')
    clients = db.relationship('Client', back_populates='messages')
    
    def __init__(self, **kwargs):
        super(Message, self).__init__(**kwargs)
        # Set read status based on direction
        if self.direction == 'outbound':
            self.is_read = True  # Outbound messages are considered "read"
    
    @property
    def is_incoming(self) -> bool:
        """Check if message is incoming"""
        return self.direction == 'inbound'
    
    @property
    def is_outgoing(self) -> bool:
        """Check if message is outgoing"""
        return self.direction == 'outbound'
    
    def mark_as_read(self) -> None:
        """Mark message as read"""
        self.is_read = True
        self.updated_at = datetime.utcnow()
    
    def mark_as_flagged(self, reason: str = None) -> None:
        """Mark message as flagged"""
        self.is_flagged = True
        if reason:
            self.error_message = reason
        self.updated_at = datetime.utcnow()
    
    def to_dict(self, include_client_info: bool = True) -> Dict[str, Any]:
        """Convert message to dictionary"""
        data = {
            'id': self.id,
            'message_sid': self.message_sid,
            'user_id': self.user_id,
            'client_id': self.client_id,
            'message_body': self.message_body,
            'sender_number': self.sender_number,
            'recipient_number': self.recipient_number,
            'direction': self.direction,
            'status': self.status,
            'is_ai_generated': self.is_ai_generated,
            'is_read': self.is_read,
            'is_flagged': self.is_flagged,
            'related_message_sid': self.related_message_sid,
            'error_message': self.error_message,
            'retry_count': self.retry_count,
            'timestamp': self.timestamp.isoformat(),
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            # Helper properties
            'is_incoming': self.is_incoming,
            'is_outgoing': self.is_outgoing
        }
        
        # Include client information if requested and available
        if include_client_info and self.client:
            data['client'] = {
                'id': self.client.id,
                'phone_number': self.client.phone_number,
                'name': self.client.name,
                'is_blocked': self.client.is_blocked
            }
        
        return data
    
    @classmethod
    def get_conversation(cls, user_id: int, client_phone: str, limit: int = 50) -> list:
        """Get conversation between user and client"""
        return cls.query.filter(
            cls.user_id == user_id,
            db.or_(
                cls.sender_number == client_phone,
                cls.recipient_number == client_phone
            )
        ).order_by(cls.timestamp.desc()).limit(limit).all()
    
    @classmethod
    def get_recent_conversations(cls, user_id: int, limit: int = 20) -> list:
        """Get recent conversations for user"""
        # Get the most recent message for each unique phone number
        subquery = db.session.query(
            cls.sender_number.label('phone'),
            db.func.max(cls.timestamp).label('last_message_time')
        ).filter(
            cls.user_id == user_id,
            cls.direction == 'inbound'
        ).group_by(cls.sender_number).subquery()
        
        # Get the actual messages
        return db.session.query(cls).join(
            subquery,
            db.and_(
                cls.sender_number == subquery.c.phone,
                cls.timestamp == subquery.c.last_message_time,
                cls.user_id == user_id
            )
        ).order_by(cls.timestamp.desc()).limit(limit).all()
    
    @classmethod
    def count_unread(cls, user_id: int) -> int:
        """Count unread messages for user"""
        return cls.query.filter(
            cls.user_id == user_id,
            cls.direction == 'inbound',
            cls.is_read == False
        ).count()
    
    @classmethod
    def get_daily_count(cls, user_id: int, date: datetime = None) -> int:
        """Get message count for a specific day"""
        if date is None:
            date = datetime.utcnow().date()
        
        start_of_day = datetime.combine(date, datetime.min.time())
        end_of_day = datetime.combine(date, datetime.max.time())
        
        return cls.query.filter(
            cls.user_id == user_id,
            cls.timestamp >= start_of_day,
            cls.timestamp <= end_of_day
        ).count()


class FlaggedMessage(db.Model):
    """Separate table for flagged message details"""
    __tablename__ = 'flagged_messages'
    
    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.Integer, db.ForeignKey('messages.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)  # UPDATED: changed from profile_id
    
    reason = db.Column(db.String(100), nullable=False)  # 'spam', 'inappropriate', 'threatening', etc.
    severity = db.Column(db.String(20), default='medium')  # 'low', 'medium', 'high', 'critical'
    
    # Review status
    is_reviewed = db.Column(db.Boolean, default=False)
    reviewed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    review_notes = db.Column(db.Text)
    
    # Auto-detection metadata
    detection_method = db.Column(db.String(50))  # 'keyword', 'ai', 'manual'
    confidence_score = db.Column(db.Float)  # For AI detection
    
    # Timestamps
    flagged_at = db.Column(db.DateTime, default=datetime.utcnow)
    reviewed_at = db.Column(db.DateTime)
    
    # Relationships
    message = db.relationship('Message', backref='flag_details')
    user = db.relationship('User', foreign_keys=[user_id])
    reviewer = db.relationship('User', foreign_keys=[reviewed_by])
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'message_id': self.message_id,
            'user_id': self.user_id,
            'reason': self.reason,
            'severity': self.severity,
            'is_reviewed': self.is_reviewed,
            'reviewed_by': self.reviewed_by,
            'review_notes': self.review_notes,
            'detection_method': self.detection_method,
            'confidence_score': self.confidence_score,
            'flagged_at': self.flagged_at.isoformat(),
            'reviewed_at': self.reviewed_at.isoformat() if self.reviewed_at else None
        }