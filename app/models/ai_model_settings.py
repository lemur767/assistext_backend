from app.extensions import db
from datetime import datetime


class AIModelSettings(db.Model):
    __tablename__ = 'ai_model_settings'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(db.Integer, db.ForeignKey('profiles.id'), nullable=False, unique=True)
    model_version = db.Column(db.String(50), default='gpt-4')
    temperature = db.Column(db.Float, default=0.7)
    response_length = db.Column(db.Integer, default=150)
    custom_instructions = db.Column(db.Text)
    style_notes = db.Column(db.Text)
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
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }