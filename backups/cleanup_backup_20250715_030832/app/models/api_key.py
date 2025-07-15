from app.extensions import db
from datetime import datetime

class APIKey(db.Model):
    __tablename__ = 'api_keys'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    key_hash = db.Column(db.String(64), unique=True, nullable=False) # Store only hash of the key
    permissions = db.Column(db.Text) # JSON string of permissions
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=True)
    revoked_at = db.Column(db.DateTime, nullable=True)
    last_used_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    user = db.relationship('User', backref=db.backref('api_keys', lazy='dynamic'))
    
    def __repr__(self):
        return f'<APIKey {self.name}>'
    
    def to_dict(self):
        import json
        
        return {
            'id': self.id,
            'user_id': self.user_id,
            'key': self.key[:8] + '...',  # Only expose first 8 chars for security
            'name': self.name,
            'permissions': json.loads(self.permissions) if self.permissions else {},
            'last_used_at': self.last_used_at.isoformat() if self.last_used_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }   