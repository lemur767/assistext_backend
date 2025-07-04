from app.extensions import db
from datetime import datetime
from typing import Dict, Any, List

class Client(db.Model):
    __tablename__ = 'clients'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Client Information
    phone_number = db.Column(db.String(20), nullable=False, index=True)
    name = db.Column(db.String(100))  # User-assigned name
    nickname = db.Column(db.String(100))  # Casual name/alias
    notes = db.Column(db.Text)  # Private notes about this client
    tags = db.Column(db.String(500))  # Comma-separated tags
    
    # Relationship Management
    relationship_status = db.Column(db.String(50), default='new')  # new, regular, vip, blocked
    priority_level = db.Column(db.Integer, default=1)  # 1-5, 5 being highest priority
    
    # Interaction Tracking
    first_contact = db.Column(db.DateTime, default=datetime.utcnow)
    last_interaction = db.Column(db.DateTime, default=datetime.utcnow)
    total_interactions = db.Column(db.Integer, default=0)
    
    # Client-Specific AI Settings (overrides user defaults)
    custom_ai_personality = db.Column(db.Text)  # Custom personality for this client
    custom_greeting = db.Column(db.Text)  # Custom greeting message
    auto_reply_enabled = db.Column(db.Boolean, default=True)
    
    # Status
    is_blocked = db.Column(db.Boolean, default=False)
    block_reason = db.Column(db.String(200))
    is_favorite = db.Column(db.Boolean, default=False)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', back_populates='clients')
    messages = db.relationship('Message', back_populates='client', lazy='dynamic', cascade='all, delete-orphan')
    
    def get_tags_list(self) -> List[str]:
        """Get tags as a list"""
        return [tag.strip() for tag in (self.tags or '').split(',') if tag.strip()]
    
    def set_tags_list(self, tags_list: List[str]) -> None:
        """Set tags from a list"""
        self.tags = ', '.join(tags_list) if tags_list else ''
    
    def update_interaction(self) -> None:
        """Update interaction timestamp and count"""
        self.last_interaction = datetime.utcnow()
        self.total_interactions += 1
    
    def get_display_name(self) -> str:
        """Get the best display name for this client"""
        return self.name or self.nickname or self.phone_number
    
    def get_ai_personality(self) -> str:
        """Get AI personality for this client (custom or user default)"""
        return self.custom_ai_personality or self.user.ai_personality or "You are a helpful assistant."
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert client to dictionary"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'phone_number': self.phone_number,
            'name': self.name,
            'nickname': self.nickname,
            'display_name': self.get_display_name(),
            'notes': self.notes,
            'tags': self.get_tags_list(),
            'relationship_status': self.relationship_status,
            'priority_level': self.priority_level,
            'first_contact': self.first_contact.isoformat(),
            'last_interaction': self.last_interaction.isoformat(),
            'total_interactions': self.total_interactions,
            'custom_ai_personality': self.custom_ai_personality,
            'custom_greeting': self.custom_greeting,
            'auto_reply_enabled': self.auto_reply_enabled,
            'is_blocked': self.is_blocked,
            'block_reason': self.block_reason,
            'is_favorite': self.is_favorite,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

