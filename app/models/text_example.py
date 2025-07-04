from app.extensions import db
from datetime import datetime
from typing import Dict, Any

class TextExample(db.Model):
    __tablename__ = 'text_examples'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Example Content
    content = db.Column(db.Text, nullable=False)
    is_incoming = db.Column(db.Boolean, nullable=False)  # True if example of incoming message
    context_note = db.Column(db.String(200))  # Note about when to use this example
    
    # Usage
    usage_count = db.Column(db.Integer, default=0)
    last_used = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', back_populates='text_examples')
    
    def mark_used(self) -> None:
        """Mark this example as used"""
        self.usage_count += 1
        self.last_used = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert text example to dictionary"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'content': self.content,
            'is_incoming': self.is_incoming,
            'context_note': self.context_note,
            'usage_count': self.usage_count,
            'last_used': self.last_used.isoformat() if self.last_used else None,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }