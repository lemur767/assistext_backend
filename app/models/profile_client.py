# app/models/profile_client.py
from app.extensions import db
from datetime import datetime


class ProfileClient(db.Model):
    __tablename__ = 'profile_clients'
    
    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(db.Integer, db.ForeignKey('profiles.id'), nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)
    
    # Profile-specific client information
    nickname = db.Column(db.String(100))  # Profile's nickname for this client
    notes = db.Column(db.Text)  # Profile-specific notes
    tags = db.Column(db.String(500))  # Comma-separated tags
    
    # Relationship status
    relationship_status = db.Column(db.String(50))  # new, regular, vip, blocked
    last_interaction = db.Column(db.DateTime)
    total_interactions = db.Column(db.Integer, default=0)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    profile = db.relationship('Profile', back_populates='profile_clients')
    client = db.relationship('Client', back_populates='profile_clients')
    
    def to_dict(self):
        return {
            'id': self.id,
            'profile_id': self.profile_id,
            'client_id': self.client_id,
            'nickname': self.nickname,
            'notes': self.notes,
            'tags': self.tags.split(',') if self.tags else [],
            'relationship_status': self.relationship_status,
            'last_interaction': self.last_interaction.isoformat() if self.last_interaction else None,
            'total_interactions': self.total_interactions,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
