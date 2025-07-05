from app.extensions import db
from datetime import datetime


class UsageMetrics(db.Model):
    __tablename__ = 'usage_metrics'
    
    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(db.Integer, db.ForeignKey('profiles.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    
    # Message counts
    messages_received = db.Column(db.Integer, default=0)
    messages_sent = db.Column(db.Integer, default=0)
    ai_responses = db.Column(db.Integer, default=0)
    auto_responses = db.Column(db.Integer, default=0)
    
    # Performance metrics
    avg_response_time = db.Column(db.Float)  # seconds
    llm_server_requests = db.Column(db.Integer, default=0)
    llm_server_failures = db.Column(db.Integer, default=0)
    openai_fallback_usage = db.Column(db.Integer, default=0)
    
    # Safety metrics
    flagged_messages = db.Column(db.Integer, default=0)
    blocked_responses = db.Column(db.Integer, default=0)
    high_risk_interactions = db.Column(db.Integer, default=0)
    
    # Engagement metrics
    unique_contacts = db.Column(db.Integer, default=0)
    conversation_starts = db.Column(db.Integer, default=0)
    conversation_length_avg = db.Column(db.Float)  # average messages per conversation
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    profile = db.relationship('Profile', foreign_keys=[profile_id])
    
    def to_dict(self):
        return {
            'id': self.id,
            'profile_id': self.profile_id,
            'date': self.date.isoformat(),
            'messages_received': self.messages_received,
            'messages_sent': self.messages_sent,
            'ai_responses': self.ai_responses,
            'auto_responses': self.auto_responses,
            'avg_response_time': self.avg_response_time,
            'llm_server_requests': self.llm_server_requests,
            'llm_server_failures': self.llm_server_failures,
            'openai_fallback_usage': self.openai_fallback_usage,
            'flagged_messages': self.flagged_messages,
            'blocked_responses': self.blocked_responses,
            'unique_contacts': self.unique_contacts,
            'conversation_starts': self.conversation_starts,
            'conversation_length_avg': self.conversation_length_avg
        }


class SystemHealth(db.Model):
    __tablename__ = 'system_health'
    
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Service status
    backend_status = db.Column(db.String(20))  # healthy, degraded, down
    llm_server_status = db.Column(db.String(20))
    database_status = db.Column(db.String(20))
    redis_status = db.Column(db.String(20))
    signalwire_status = db.Column(db.String(20))
    
    # Performance metrics
    response_time_p95 = db.Column(db.Float)  # 95th percentile response time
    memory_usage_percent = db.Column(db.Float)
    cpu_usage_percent = db.Column(db.Float)
    disk_usage_percent = db.Column(db.Float)
    
    # Queue metrics
    celery_queue_length = db.Column(db.Integer)
    celery_failed_tasks = db.Column(db.Integer)
    
    # Error rates
    webhook_error_rate = db.Column(db.Float)  # percent
    ai_generation_error_rate = db.Column(db.Float)
    
    def to_dict(self):
        return {
            'timestamp': self.timestamp.isoformat(),
            'backend_status': self.backend_status,
            'llm_server_status': self.llm_server_status,
            'database_status': self.database_status,
            'redis_status': self.redis_status,
            'signalwire_status': self.signalwire_status,
            'response_time_p95': self.response_time_p95,
            'memory_usage_percent': self.memory_usage_percent,
            'cpu_usage_percent': self.cpu_usage_percent,
            'disk_usage_percent': self.disk_usage_percent,
            'celery_queue_length': self.celery_queue_length,
            'webhook_error_rate': self.webhook_error_rate,
            'ai_generation_error_rate': self.ai_generation_error_rate
        }