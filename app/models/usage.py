
from app.extensions import db
from datetime import datetime

class UseageRecord(db.Model):
    """Usage tracking model"""
    __tablename__ = 'usage'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    subscription_id = db.Column(db.Integer, db.ForeignKey('subscriptions.id'), nullable=False)
    
    # Period
    period_start = db.Column(db.DateTime, nullable=False)
    period_end = db.Column(db.DateTime, nullable=False)
    
    # SMS Usage
    sms_sent = db.Column(db.Integer, default=0)
    sms_received = db.Column(db.Integer, default=0)
    sms_credits_used = db.Column(db.Integer, default=0)
    sms_credits_remaining = db.Column(db.Integer, default=0)
    
    # AI Usage
    ai_responses_generated = db.Column(db.Integer, default=0)
    ai_credits_used = db.Column(db.Integer, default=0)
    ai_credits_remaining = db.Column(db.Integer, default=0)
    
    # Profile Usage
    active_profiles = db.Column(db.Integer, default=0)
    total_conversations = db.Column(db.Integer, default=0)
    
    # Storage Usage
    storage_used_gb = db.Column(db.Numeric(10, 3), default=0.0)
    storage_limit_gb = db.Column(db.Numeric(10, 3), default=0.0)
    
    # API Usage
    api_calls_made = db.Column(db.Integer, default=0)
    api_calls_limit = db.Column(db.Integer, default=0)
    
    # Advanced Features Usage
    webhook_calls = db.Column(db.Integer, default=0)
    integration_syncs = db.Column(db.Integer, default=0)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', back_populates='useage_records')
    overages = db.relationship('UsageOverage', backref='usage', lazy='dynamic', cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'user_id': self.user_id,
            'subscription_id': self.subscription_id,
            'period_start': self.period_start.isoformat() if self.period_start else None,
            'period_end': self.period_end.isoformat() if self.period_end else None,
            'sms_sent': self.sms_sent,
            'sms_received': self.sms_received,
            'sms_credits_used': self.sms_credits_used,
            'sms_credits_remaining': self.sms_credits_remaining,
            'ai_responses_generated': self.ai_responses_generated,
            'ai_credits_used': self.ai_credits_used,
            'ai_credits_remaining': self.ai_credits_remaining,
            'active_profiles': self.active_profiles,
            'total_conversations': self.total_conversations,
            'storage_used_gb': float(self.storage_used_gb) if self.storage_used_gb else 0.0,
            'storage_limit_gb': float(self.storage_limit_gb) if self.storage_limit_gb else 0.0,
            'api_calls_made': self.api_calls_made,
            'api_calls_limit': self.api_calls_limit,
            'webhook_calls': self.webhook_calls,
            'integration_syncs': self.integration_syncs,
            'last_updated': self.last_updated.isoformat() if self.last_updated else None,
            'overages': [overage.to_dict() for overage in self.overages]
        }


class UsageOverage(db.Model):
    """Usage overage tracking"""
    __tablename__ = 'usage_overages'
    
    id = db.Column(db.String(50), primary_key=True)
    usage_id = db.Column(db.Integer, db.ForeignKey('usage.id'), nullable=False)
    
    # Overage details
    metric = db.Column(db.String(50), nullable=False)  # sms_credits, ai_credits, etc.
    overage_amount = db.Column(db.Integer, nullable=False)
    overage_cost = db.Column(db.Numeric(10, 2), nullable=False)
    rate_per_unit = db.Column(db.Numeric(10, 4), nullable=False)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'usage_id': self.usage_id,
            'metric': self.metric,
            'overage_amount': self.overage_amount,
            'overage_cost': float(self.overage_cost),
            'rate_per_unit': float(self.rate_per_unit),
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
