from app.extensions import db
from datetime import datetime


class TextExample(db.Model):
    __tablename__ = 'text_examples'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(db.Integer, db.ForeignKey('profiles.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_incoming = db.Column(db.Boolean, default=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    profile = db.relationship('Profile', back_populates='text_examples')
    
    def to_dict(self):
        return {
            'id': self.id,
            'profile_id': self.profile_id,
            'content': self.content,
            'is_incoming': self.is_incoming,
            'timestamp': self.timestamp.isoformat()
        }