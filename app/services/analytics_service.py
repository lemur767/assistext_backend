"""
Analytics Service for tracking usage, performance, and business metrics.
"""

from datetime import timedelta, date
from typing import Dict
from flask import current_app


from app.extensions import db


class AnalyticsService:
    """Service for handling analytics and reporting."""
    
    @staticmethod
    def get_user_overview(user_id: int) -> Dict:
        """Get overview statistics for a user."""
        # Lazy import to avoid circular imports
        from app.models.user import User
        from app.models.profile import Profile
        from app.models.message import Message
        from app.models.billing import Subscription
        from app.models.flagged_message import FlaggedMessage
        
        user = User.query.get(user_id)
        if not user:
            return {}
        
        # Get user's profiles
        profiles = Profile.query.filter_by(user_id=user_id).all()
        profile_ids = [p.id for p in profiles]
        
        # Get active subscription
        subscription = Subscription.query.filter_by(
            user_id=user_id,
            is_active=True
        ).first()
        
        # Calculate date ranges
        today = date.today()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        
        # Get message statistics
        total_messages = Message.query.filter(
            Message.profile_id.in_(profile_ids)
        ).count() if profile_ids else 0
        
        messages_this_week = Message.query.filter(
            Message.profile_id.in_(profile_ids),
            Message.timestamp >= week_ago
        ).count() if profile_ids else 0
        
        messages_this_month = Message.query.filter(
            Message.profile_id.in_(profile_ids),
            Message.timestamp >= month_ago
        ).count() if profile_ids else 0
        
        # AI responses
        ai_responses_total = Message.query.filter(
            Message.profile_id.in_(profile_ids),
            Message.ai_generated == True,
            Message.is_incoming == False
        ).count() if profile_ids else 0
        
        ai_responses_this_month = Message.query.filter(
            Message.profile_id.in_(profile_ids),
            Message.ai_generated == True,
            Message.is_incoming == False,
            Message.timestamp >= month_ago
        ).count() if profile_ids else 0
        
        # Get unique clients
        unique_clients = db.session.query(Message.sender_number).filter(
            Message.profile_id.in_(profile_ids)
        ).distinct().count() if profile_ids else 0
        
        # Flagged messages
        flagged_count = db.session.query(FlaggedMessage).join(Message).filter(
            Message.profile_id.in_(profile_ids),
            FlaggedMessage.is_reviewed == False
        ).count() if profile_ids else 0
        
        return {
            'user_id': user_id,
            'profiles_count': len(profiles),
            'subscription': subscription.to_dict() if subscription else None,
            'messages': {
                'total': total_messages,
                'this_week': messages_this_week,
                'this_month': messages_this_month
            },
            'ai_responses': {
                'total': ai_responses_total,
                'this_month': ai_responses_this_month
            },
            'unique_clients': unique_clients,
            'flagged_messages': flagged_count,
            'created_at': user.created_at.isoformat()
        }