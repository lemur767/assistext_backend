# app/models/signalwire.py
from datetime import datetime
from app.extensions import db

class SignalWireSubproject(db.Model):
    __tablename__ = 'signalwire_subprojects'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    subproject_id = db.Column(db.String(100), nullable=False)
    subproject_name = db.Column(db.String(200))
    auth_token = db.Column(db.String(200))  # Store encrypted in production
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<SignalWireSubproject {self.subproject_name}>'

class SignalWirePhoneNumber(db.Model):
    __tablename__ = 'signalwire_phone_numbers'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    subproject_id = db.Column(db.String(100))
    phone_number_sid = db.Column(db.String(100), nullable=False)
    phone_number = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), default='active')  # active, inactive, suspended
    purchased_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<SignalWirePhoneNumber {self.phone_number}>'