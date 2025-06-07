# app/models/text_example.py
from app.extensions import db
from datetime import datetime


class TextExample(db.Model):
    __tablename__ = 'text_examples'
    
    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(db.Integer, db.ForeignKey('profiles.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_incoming = db.Column(db.Boolean, nullable=False)  # True if from client, False if from profile
    context_note = db.Column(db.String(200))  # Optional context about this example
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    profile = db.relationship('Profile', back_populates='text_examples')
    
    def to_dict(self):
        return {
            'id': self.id,
            'profile_id': self.profile_id,
            'content': self.content,
            'is_incoming': self.is_incoming,
            'context_note': self.context_note,
            'timestamp': self.timestamp.isoformat()
        }
