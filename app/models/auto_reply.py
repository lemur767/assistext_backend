# app/models/auto_reply.py
from app.extensions import db
from datetime import datetime


class AutoReply(db.Model):
    __tablename__ = 'auto_replies'
    
    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(db.Integer, db.ForeignKey('profiles.id'), nullable=False)
    keyword = db.Column(db.String(100), nullable=False)
    response = db.Column(db.Text, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    priority = db.Column(db.Integer, default=0)  # Higher priority triggers first
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    profile = db.relationship('Profile', back_populates='auto_replies')
    
    def to_dict(self):
        return {
            'id': self.id,
            'profile_id': self.profile_id,
            'keyword': self.keyword,
            'response': self.response,
            'is_active': self.is_active,
            'priority': self.priority,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
