from app.extensions import db
from datetime import datetime

class ProfileClient(db.Model):
    __tablename__ = 'profile_clients'
    
    profile_id = db.Column(db.Integer, db.ForeignKey('profiles.id'), primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), primary_key=True)
    notes = db.Column(db.Text)
    last_contact = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    profile = db.relationship('Profile', back_populates='profile_clients')
    client = db.relationship('Client', back_populates='profile_clients')
    
    __table_args__ = (
        db.UniqueConstraint('profile_id', 'client_id', name='uix_profile_client'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'profile_id': self.profile_id,
            'client_id': self.client_id,
            'notes': self.notes,
            'last_contact': self.last_contact.isoformat() if self.last_contact else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }