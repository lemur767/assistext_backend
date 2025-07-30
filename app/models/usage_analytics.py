from app.extensions import db
from datetime import datetime
import uuid

class UsageAnalytics(db.Model):
    """Monthly usage analytics tracking"""
    __tablename__ = 'usage_analytics'
    
    id = db.Column(db.String(50), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(50), db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    month = db.Column(db.Integer, nullable=False)
    year = db.Column(db.Integer, nullable=False)
    
    # Message metrics
    messages_sent = db.Column(db.Integer, default=0)
    messages_received = db.Column(db.Integer, default=0)
    ai_responses_generated = db.Column(db.Integer, default=0)
    templates_used = db.Column(db.Integer, default=0)
    
    # Conversation metrics
    unique_conversations = db.Column(db.Integer, default=0)
    avg_response_time = db.Column(db.Integer)  # in seconds
    sentiment_avg = db.Column(db.Numeric(3, 2))
    engagement_score = db.Column(db.Numeric(3, 2))
    
    # Peak activity
    peak_hour = db.Column(db.Integer)
    peak_day = db.Column(db.String(10))
    
    # Cost tracking
    total_cost = db.Column(db.Numeric(10, 2), default=0)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref='usage_analytics')
    
    # Unique constraint
    __table_args__ = (
        db.UniqueConstraint('user_id', 'year', 'month', name='unique_user_month'),
        db.Index('idx_usage_analytics_user_month', 'user_id', 'year', 'month'),
    )
    
    def __init__(self, user_id, month, year):
        self.user_id = user_id
        self.month = month
        self.year = year
    
    @classmethod
    def get_or_create(cls, user_id, year=None, month=None):
        """Get existing record or create new one for current/specified month"""
        now = datetime.utcnow()
        if year is None:
            year = now.year
        if month is None:
            month = now.month
        
        record = cls.query.filter_by(
            user_id=user_id,
            year=year,
            month=month
        ).first()
        
        if not record:
            record = cls(user_id=user_id, year=year, month=month)
            db.session.add(record)
            db.session.commit()
        
        return record
    
    @classmethod
    def get_user_analytics(cls, user_id, months=12):
        """Get analytics for user for specified number of months"""
        return cls.query.filter_by(user_id=user_id)\
                       .order_by(cls.year.desc(), cls.month.desc())\
                       .limit(months).all()
    
    def update_message_sent(self, count=1, ai_generated=False):
        """Update sent message count"""
        self.messages_sent += count
        if ai_generated:
            self.ai_responses_generated += count
        db.session.commit()
    
    def update_message_received(self, count=1):
        """Update received message count"""
        self.messages_received += count
        db.session.commit()
    
    def update_cost(self, additional_cost):
        """Update total cost"""
        self.total_cost = (self.total_cost or 0) + additional_cost
        db.session.commit()
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'month': self.month,
            'year': self.year,
            'messages_sent': self.messages_sent,
            'messages_received': self.messages_received,
            'ai_responses_generated': self.ai_responses_generated,
            'templates_used': self.templates_used,
            'unique_conversations': self.unique_conversations,
            'avg_response_time': self.avg_response_time,
            'sentiment_avg': float(self.sentiment_avg) if self.sentiment_avg else None,
            'engagement_score': float(self.engagement_score) if self.engagement_score else None,
            'peak_hour': self.peak_hour,
            'peak_day': self.peak_day,
            'total_cost': float(self.total_cost) if self.total_cost else 0,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    def __repr__(self):
        return f'<UsageAnalytics {self.user_id} {self.year}-{self.month}>'

class ConversationAnalytics(db.Model):
    """Per-conversation analytics tracking"""
    __tablename__ = 'conversation_analytics'
    
    id = db.Column(db.String(50), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(50), db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    client_id = db.Column(db.String(50), db.ForeignKey('clients.id', ondelete='CASCADE'), nullable=False)
    phone_number = db.Column(db.String(20), nullable=False)
    
    # Message metrics
    total_messages = db.Column(db.Integer, default=0)
    ai_responses = db.Column(db.Integer, default=0)
    response_rate = db.Column(db.Numeric(3, 2), default=0)
    
    # Performance metrics
    avg_response_time = db.Column(db.Integer)  # in seconds
    sentiment_score = db.Column(db.Numeric(3, 2), default=0)
    engagement_score = db.Column(db.Numeric(3, 2), default=0)
    
    # Activity tracking
    last_interaction = db.Column(db.DateTime)
    conversation_status = db.Column(db.String(50), default='active')
    
    # Analytics data (JSON)
    peak_hours = db.Column(db.JSON)
    daily_stats = db.Column(db.JSON)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref='conversation_analytics')
    client = db.relationship('Client', backref='conversation_analytics')
    
    # Indexes
    __table_args__ = (
        db.Index('idx_conversation_analytics_user_client', 'user_id', 'client_id'),
        db.Index('idx_conversation_analytics_phone', 'phone_number'),
        db.Index('idx_conversation_analytics_updated', 'updated_at'),
    )
    
    def __init__(self, user_id, client_id, phone_number):
        self.user_id = user_id
        self.client_id = client_id
        self.phone_number = phone_number
        self.last_interaction = datetime.utcnow()
    
    @classmethod
    def get_or_create(cls, user_id, client_id, phone_number):
        """Get existing conversation analytics or create new one"""
        record = cls.query.filter_by(
            user_id=user_id,
            client_id=client_id,
            phone_number=phone_number
        ).first()
        
        if not record:
            record = cls(
                user_id=user_id,
                client_id=client_id,
                phone_number=phone_number
            )
            db.session.add(record)
            db.session.commit()
        
        return record
    
    @classmethod
    def get_user_conversations(cls, user_id, active_only=True):
        """Get all conversation analytics for a user"""
        query = cls.query.filter_by(user_id=user_id)
        
        if active_only:
            query = query.filter_by(conversation_status='active')
        
        return query.order_by(cls.last_interaction.desc()).all()
    
    @classmethod
    def get_top_conversations(cls, user_id, limit=10, order_by='engagement_score'):
        """Get top conversations by specified metric"""
        order_column = getattr(cls, order_by, cls.engagement_score)
        
        return cls.query.filter_by(user_id=user_id)\
                       .order_by(order_column.desc())\
                       .limit(limit).all()
    
    def add_message(self, is_ai_generated=False, response_time=None):
        """Add a message to the conversation analytics"""
        self.total_messages += 1
        
        if is_ai_generated:
            self.ai_responses += 1
        
        if response_time:
            # Update rolling average response time
            if self.avg_response_time:
                self.avg_response_time = int((self.avg_response_time + response_time) / 2)
            else:
                self.avg_response_time = response_time
        
        # Update response rate
        if self.total_messages > 0:
            self.response_rate = round(self.ai_responses / self.total_messages, 2)
        
        self.last_interaction = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        
        db.session.commit()
    
    def update_sentiment(self, sentiment_score):
        """Update sentiment score (rolling average)"""
        if self.sentiment_score:
            self.sentiment_score = round((float(self.sentiment_score) + sentiment_score) / 2, 2)
        else:
            self.sentiment_score = round(sentiment_score, 2)
        
        db.session.commit()
    
    def update_engagement(self, engagement_score):
        """Update engagement score"""
        self.engagement_score = round(engagement_score, 2)
        self.updated_at = datetime.utcnow()
        db.session.commit()
    
    def update_peak_hours(self, hour):
        """Update peak hours statistics"""
        if not self.peak_hours:
            self.peak_hours = {}
        
        hour_str = str(hour)
        self.peak_hours[hour_str] = self.peak_hours.get(hour_str, 0) + 1
        
        # Keep only top 5 peak hours
        if len(self.peak_hours) > 5:
            sorted_hours = sorted(self.peak_hours.items(), key=lambda x: x[1], reverse=True)
            self.peak_hours = dict(sorted_hours[:5])
        
        db.session.commit()
    
    def update_daily_stats(self, date_str, message_type='received'):
        """Update daily statistics"""
        if not self.daily_stats:
            self.daily_stats = {}
        
        if date_str not in self.daily_stats:
            self.daily_stats[date_str] = {'sent': 0, 'received': 0}
        
        self.daily_stats[date_str][message_type] += 1
        
        # Keep only last 30 days
        if len(self.daily_stats) > 30:
            sorted_dates = sorted(self.daily_stats.keys(), reverse=True)
            self.daily_stats = {date: self.daily_stats[date] for date in sorted_dates[:30]}
        
        db.session.commit()
    
    def calculate_engagement_score(self):
        """Calculate engagement score based on various factors"""
        # Basic engagement calculation
        base_score = 0
        
        # Response rate factor (40% weight)
        if self.response_rate:
            base_score += float(self.response_rate) * 0.4
        
        # Message frequency factor (30% weight)
        if self.total_messages:
            # Normalize message count (assume 50+ messages = high engagement)
            msg_factor = min(self.total_messages / 50, 1.0)
            base_score += msg_factor * 0.3
        
        # Recency factor (20% weight)
        if self.last_interaction:
            days_since_last = (datetime.utcnow() - self.last_interaction).days
            recency_factor = max(0, 1 - (days_since_last / 30))  # 30 day decay
            base_score += recency_factor * 0.2
        
        # Sentiment factor (10% weight)
        if self.sentiment_score and self.sentiment_score > 0:
            base_score += float(self.sentiment_score) * 0.1
        
        return round(min(base_score, 1.0), 2)
    
    def mark_inactive(self):
        """Mark conversation as inactive"""
        self.conversation_status = 'inactive'
        self.updated_at = datetime.utcnow()
        db.session.commit()
    
    def to_dict(self, include_stats=True):
        """Convert to dictionary"""
        data = {
            'id': self.id,
            'user_id': self.user_id,
            'client_id': self.client_id,
            'phone_number': self.phone_number,
            'total_messages': self.total_messages,
            'ai_responses': self.ai_responses,
            'response_rate': float(self.response_rate) if self.response_rate else 0,
            'avg_response_time': self.avg_response_time,
            'sentiment_score': float(self.sentiment_score) if self.sentiment_score else 0,
            'engagement_score': float(self.engagement_score) if self.engagement_score else 0,
            'last_interaction': self.last_interaction.isoformat() if self.last_interaction else None,
            'conversation_status': self.conversation_status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
        
        if include_stats:
            data.update({
                'peak_hours': self.peak_hours or {},
                'daily_stats': self.daily_stats or {}
            })
        
        return data
    
    def __repr__(self):
        return f'<ConversationAnalytics {self.user_id}:{self.phone_number}>'

class AnalyticsTracker:
    """Utility class for tracking analytics events"""
    
    @staticmethod
    def track_message_sent(user_id, client_id, phone_number, ai_generated=False, response_time=None):
        """Track a sent message"""
        
        # Update usage analytics
        usage = UsageAnalytics.get_or_create(user_id)
        usage.update_message_sent(ai_generated=ai_generated)
        
        # Update conversation analytics
        conversation = ConversationAnalytics.get_or_create(user_id, client_id, phone_number)
        conversation.add_message(is_ai_generated=ai_generated, response_time=response_time)
        
        # Update peak hours
        current_hour = datetime.utcnow().hour
        conversation.update_peak_hours(current_hour)
        
        # Update daily stats
        today = datetime.utcnow().strftime('%Y-%m-%d')
        conversation.update_daily_stats(today, 'sent')
    
    @staticmethod
    def track_message_received(user_id, client_id, phone_number):
        """Track a received message"""
        
        # Update usage analytics
        usage = UsageAnalytics.get_or_create(user_id)
        usage.update_message_received()
        
        # Update conversation analytics
        conversation = ConversationAnalytics.get_or_create(user_id, client_id, phone_number)
        conversation.add_message()
        
        # Update daily stats
        today = datetime.utcnow().strftime('%Y-%m-%d')
        conversation.update_daily_stats(today, 'received')
    
    @staticmethod
    def update_sentiment(user_id, client_id, phone_number, sentiment_score):
        """Update conversation sentiment"""
        conversation = ConversationAnalytics.get_or_create(user_id, client_id, phone_number)
        conversation.update_sentiment(sentiment_score)
    
    @staticmethod
    def update_engagement(user_id, client_id, phone_number):
        """Recalculate and update engagement score"""
        conversation = ConversationAnalytics.get_or_create(user_id, client_id, phone_number)
        engagement_score = conversation.calculate_engagement_score()
        conversation.update_engagement(engagement_score)
    
    @staticmethod
    def track_cost(user_id, cost):
        """Track usage cost"""
        usage = UsageAnalytics.get_or_create(user_id)
        usage.update_cost(cost)