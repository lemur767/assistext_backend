from app.extensions import db
from datetime import datetime


class UsageRecord(db.Model):
    __tablename__ = 'usage_records'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    profile_id = db.Column(db.Integer, db.ForeignKey('profiles.id'))
    subscription_id = db.Column(db.Integer, db.ForeignKey('subscriptions.id'))
    date = db.Column(db.Date, nullable=False)
    incoming_messages = db.Column(db.Integer, default=0)
    outgoing_messages = db.Column(db.Integer, default=0)
    ai_responses = db.Column(db.Integer, default=0)
    flagged_messages = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User')
    profile = db.relationship('Profile')
    subscription = db.relationship('Subscription')
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'profile_id': self.profile_id,
            'subscription_id': self.subscription_id,
            'date': self.date.isoformat(),
            'incoming_messages': self.incoming_messages,
            'outgoing_messages': self.outgoing_messages,
            'ai_responses': self.ai_responses,
            'flagged_messages': self.flagged_messages,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }


class ActivityLog(db.Model):
    __tablename__ = 'activity_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    action = db.Column(db.String(100), nullable=False)
    entity_type = db.Column(db.String(50))
    entity_id = db.Column(db.Integer)
    details = db.Column(db.Text)  # JSON string of additional details
    ip_address = db.Column(db.String(50))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User')
    
    def to_dict(self):
        import json
        
        return {
            'id': self.id,
            'user_id': self.user_id,
            'action': self.action,
            'entity_type': self.entity_type,
            'entity_id': self.entity_id,
            'details': json.loads(self.details) if self.details else {},
            'ip_address': self.ip_address,
            'timestamp': self.timestamp.isoformat()
        }