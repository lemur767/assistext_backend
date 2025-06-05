# app/models/ai_model_settings.py
from app.extensions import db
from datetime import datetime


class AIModelSettings(db.Model):
    __tablename__ = 'ai_model_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(db.Integer, db.ForeignKey('profiles.id'), nullable=False)
    
    # Model configuration for air-gapped LLM
    model_version = db.Column(db.String(50), default='llama2')
    temperature = db.Column(db.Float, default=0.7)
    response_length = db.Column(db.Integer, default=150)  # max tokens
    
    # Personality and style
    custom_instructions = db.Column(db.Text)
    style_notes = db.Column(db.Text)
    
    # Safety settings
    safety_level = db.Column(db.String(20), default='strict')
    content_filter_enabled = db.Column(db.Boolean, default=True)
    
    # Performance settings
    response_timeout = db.Column(db.Integer, default=30)
    retry_attempts = db.Column(db.Integer, default=2)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    profile = db.relationship('Profile', back_populates='ai_settings')
    
    def to_dict(self):
        return {
            'id': self.id,
            'profile_id': self.profile_id,
            'model_version': self.model_version,
            'temperature': self.temperature,
            'response_length': self.response_length,
            'custom_instructions': self.custom_instructions,
            'style_notes': self.style_notes,
            'safety_level': self.safety_level,
            'content_filter_enabled': self.content_filter_enabled,
            'response_timeout': self.response_timeout,
            'retry_attempts': self.retry_attempts,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

