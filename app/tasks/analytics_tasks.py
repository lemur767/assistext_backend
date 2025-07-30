from celery import Celery
from app.models.usage_analytics import UsageAnalytics, ConversationAnalytics, AnalyticsTracker
from app.models.user import User
from app.extensions import db
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

@celery.task(bind=True)
def update_monthly_analytics():
    '''Update monthly analytics for all users'''
    try:
        # Get all active users
        users = User.query.filter_by(is_active=True).all()
        
        for user in users:
            # Update usage analytics for current month
            current_usage = UsageAnalytics.get_or_create(user.id)
            
            # Recalculate engagement scores
            conversations = ConversationAnalytics.get_user_conversations(user.id)
            for conv in conversations:
                AnalyticsTracker.update_engagement(user.id, conv.client_id, conv.phone_number)
            
            logger.info(f"Updated analytics for user {user.id}")
        
        logger.info(f"Updated analytics for {len(users)} users")
        
    except Exception as e:
        logger.error(f"Error updating monthly analytics: {str(e)}")
        raise

@celery.task(bind=True)
def cleanup_old_analytics():
    '''Clean up old analytics data'''
    try:
        # Keep only last 24 months of usage analytics
        cutoff_date = datetime.utcnow() - timedelta(days=730)
        
        old_usage = UsageAnalytics.query.filter(
            UsageAnalytics.created_at < cutoff_date
        ).all()
        
        for record in old_usage:
            db.session.delete(record)
        
        db.session.commit()
        logger.info(f"Cleaned up {len(old_usage)} old usage analytics records")
        
    except Exception as e:
        logger.error(f"Error cleaning up analytics: {str(e)}")
        raise