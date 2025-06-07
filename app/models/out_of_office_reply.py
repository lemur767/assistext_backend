# app/models/out_of_office_reply.py
from app.extensions import db
from datetime import datetime


class OutOfOfficeReply(db.Model):
    __tablename__ = 'out_of_office_replies'
    
    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(db.Integer, db.ForeignKey('profiles.id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    profile = db.relationship('Profile', back_populates='out_of_office_replies')
    
    def to_dict(self):
        return {
            'id': self.id,
            'profile_id': self.profile_id,
            'message': self.message,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }