# app/models/twilio_usage.py
from app.extensions import db
from datetime import datetime

class TwilioUsage(db.Model):
    __tablename__ = 'twilio_usage'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    sms_count = db.Column(db.Integer, default=0)
    voice_minutes = db.Column(db.Float, default=0.0)
    phone_numbers = db.Column(db.Integer, default=0)
    last_bill_date = db.Column(db.DateTime, nullable=True)
    current_bill_amount = db.Column(db.Float, default=0.0)
    last_bill_amount = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', back_populates='twilio_usage_tracker')
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'sms_count': self.sms_count,
            'voice_minutes': self.voice_minutes,
            'phone_numbers': self.phone_numbers,
            'last_bill_date': self.last_bill_date.isoformat() if self.last_bill_date else None,
            'current_bill_amount': self.current_bill_amount,
            'last_bill_amount': self.last_bill_amount,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }