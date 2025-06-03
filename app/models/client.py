from app.extensions import db
from datetime import datetime

class Client(db.Model):
    __tablename__ = 'clients'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    phone_number = db.Column(db.String(20), nullable=False, unique=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(255))
    notes = db.Column(db.Text)
    is_blocked = db.Column(db.Boolean, default=False)
    is_regular = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    profile_clients = db.relationship('ProfileClient', back_populates='client')
    profiles = db.relationship('Profile', secondary='profile_clients', viewonly=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'phone_number': self.phone_number,
            'name': self.name,
            'email': self.email,
            'notes': self.notes,
            'is_blocked': self.is_blocked,
            'is_regular': self.is_regular,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }