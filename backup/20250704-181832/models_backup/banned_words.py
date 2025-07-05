from app.extensions import db
from datetime import datetime


class BannedWord(db.Model):
    __tablename__ = 'banned_words'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    word = db.Column(db.String(100), nullable=False, unique=True)
    category = db.Column(db.String(50))
    severity = db.Column(db.Integer, default=1)  # 1=low, 5=high
    action = db.Column(db.String(20), default='flag')  # flag, block, ignore
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'word': self.word,
            'category': self.category,
            'severity': self.severity,
            'action': self.action,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }