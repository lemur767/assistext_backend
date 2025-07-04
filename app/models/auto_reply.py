from app.extensions import db
from datetime import datetime
from typing import Dict, Any

class AutoReply(db.Model):
    __tablename__ = 'auto_replies'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Trigger and Response
    trigger_keyword = db.Column(db.String(100), nullable=False)  # What triggers this reply
    response_message = db.Column(db.Text, nullable=False)  # What to send back
    
    # Configuration
    is_exact_match = db.Column(db.Boolean, default=False)  # Exact match vs contains
    is_case_sensitive = db.Column(db.Boolean, default=False)
    priority = db.Column(db.Integer, default=1)  # Higher priority replies checked first
    
    # Usage Tracking
    usage_count = db.Column(db.Integer, default=0)
    last_used = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', back_populates='auto_replies')
    
    def matches_message(self, message_content: str) -> bool:
        """Check if this auto-reply matches the given message"""
        if not self.is_active:
            return False
            
        trigger = self.trigger_keyword
        content = message_content
        
        if not self.is_case_sensitive:
            trigger = trigger.lower()
            content = content.lower()
        
        if self.is_exact_match:
            return content.strip() == trigger.strip()
        else:
            return trigger in content
    
    def mark_used(self) -> None:
        """Mark this auto-reply as used"""
        self.usage_count += 1
        self.last_used = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert auto-reply to dictionary"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'trigger_keyword': self.trigger_keyword,
            'response_message': self.response_message,
            'is_exact_match': self.is_exact_match,
            'is_case_sensitive': self.is_case_sensitive,
            'priority': self.priority,
            'usage_count': self.usage_count,
            'last_used': self.last_used.isoformat() if self.last_used else None,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }