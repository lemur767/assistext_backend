# app/tasks/billing.py
from app.models.user import User
from app.services.usage_tracker import UsageTracker
from app.models.usage import UsageOverage, UseageRecord
from app.services.signalwire_service import SignalWireService
from app.extensions import db
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

def update_all_usage_tracking():
    """Update usage tracking for all users with Twilio accounts"""
    logger.info("Starting usage tracking update for all users")
    
    # Get all users with Twilio accounts
    users = User.query.filter(User.signalwire_subproject_id.isnot(None)).all()
    
    for user in users:
        try:
            # Skip external accounts if they don't have API keys
            if not user.signalwire_subproject_id or not user.signalwire_subproject_token:
                logger.warning(f"User {user.id} does not have SignalWire API keys - skipping")
                continue
                
            # Create Twilio service for this user
            signalwire_service = SignalWireService(user)
            
            # Update usage tracking
            success, result = signalwire_service.update_usage_tracking()
            
            if success:
                logger.info(f"Updated usage tracking for user {user.id}")
            else:
                logger.error(f"Failed to update usage tracking for user {user.id}: {result}")
                
        except Exception as e:
            logger.exception(f"Error updating usage tracking for user {user.id}: {str(e)}")
    
    logger.info("Completed usage tracking update for all users")

def process_monthly_billing():
    """Process monthly billing for all users with Twilio accounts"""
    logger.info("Starting monthly billing process")
    
    # Get all users with Twilio accounts and usage trackers
    users = User.query.join(UseageRecord).filter(User.signalwire_subproject_id_sid.isnot(None)).all()
    
    today = datetime.today()
    
    for user in users:
        try:
            # Skip if we've already billed this month
            if (user.usage_tracker.last_bill_date and 
                user.usage_tracker.last_bill_date.month == today.month and
                user.usage_tracker.last_bill_date.year == today.year):
                logger.info(f"User {user.id} already billed this month - skipping")
                continue
                
            # Create Twilio service for this user
            signalwire_service = SignalWireService(user)
            
            # Update usage tracking
            signalwire_service.update_usage_tracking() = signalwire_service.update_usage_tracking()
            
            # Update usage tracking one final time
            signalwire_service.update_usage_tracking()
            
            # Calculate bill amount
            bill_amount = user.usage_tracker.current_bill_amount
            
            # Process billing - this would integrate with your payment processor
            # For now, we'll just update the records
            
            # Update billing records
            user.usage_tracker.last_bill_amount = bill_amount
            user.usage_tracker.last_bill_date = today
            user.usage_tracker.sms_count = 0  # Reset counters for new month
            user.usage_tracker.current_bill_amount = 0
            
            db.session.commit()
            
            logger.info(f"Processed billing for user {user.id} - amount: ${bill_amount:.2f}")
                
        except Exception as e:
            logger.exception(f"Error processing billing for user {user.id}: {str(e)}")
    
    logger.info("Completed monthly billing process")