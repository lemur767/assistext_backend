# app/models/client.py - Updated Client model

from app.extensions import db
from datetime import datetime

class Client(db.Model):
    __tablename__ = 'clients'
    
    id = db.Column(db.Integer, primary_key=True)
    phone_number = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(100))
    email = db.Column(db.String(255))
    notes = db.Column(db.Text)
    
    # Client status and categorization
    is_regular = db.Column(db.Boolean, default=False)
    is_blocked = db.Column(db.Boolean, default=False)
    is_flagged = db.Column(db.Boolean, default=False)
    risk_level = db.Column(db.String(20), default='low')  # low, medium, high
    
    # Interaction tracking
    total_messages = db.Column(db.Integer, default=0)
    first_contact = db.Column(db.DateTime, default=datetime.utcnow)
    last_contact = db.Column(db.DateTime, default=datetime.utcnow)
    last_ai_response = db.Column(db.DateTime)
    
    # Geographic and device info
    city = db.Column(db.String(100))
    state = db.Column(db.String(50))
    country = db.Column(db.String(50), default='CA')
    timezone = db.Column(db.String(50))
    device_type = db.Column(db.String(50))
    
    # Communication preferences
    preferred_communication_time = db.Column(db.String(50))
    response_preference = db.Column(db.String(20), default='quick')
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'phone_number': self.phone_number,
            'name': self.name,
            'email': self.email,
            'notes': self.notes,
            'is_regular': self.is_regular,
            'is_blocked': self.is_blocked,
            'is_flagged': self.is_flagged,
            'risk_level': self.risk_level,
            'total_messages': self.total_messages,
            'first_contact': self.first_contact.isoformat() if self.first_contact else None,
            'last_contact': self.last_contact.isoformat() if self.last_contact else None,
            'city': self.city,
            'state': self.state,
            'country': self.country,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }