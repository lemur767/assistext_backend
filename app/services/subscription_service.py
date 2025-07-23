"""
Subscription Service with Unified SignalWire Integration
"""
from app.models.billing import Subscription
from app.models.signalwire_account import SignalWireAccount, SignalWirePhoneNumber
from app.models.user import User
from app.extensions import db
from flask import current_app
from datetime import datetime, timedelta
import secrets

# Use unified SignalWire service
from app.services.signalwire_service import get_signalwire_service

class SubscriptionService:
    """Service for managing subscriptions with SignalWire integration"""
    
    @staticmethod
    def create_subscription_with_signalwire(user_id: int, plan_id: int):
        """Create subscription and set up complete SignalWire integration"""
        try:
            user = User.query.get(user_id)
            if not user:
                return False, "User not found"
            
            # Use unified service for complete tenant setup
            signalwire = get_signalwire_service()
            
            setup_result = signalwire.setup_new_tenant(
                user_id=user_id,
                friendly_name=f"{user.first_name}_{user.last_name}",
                phone_search_criteria={
                    'country': 'US',
                    'limit': 5
                }
            )
            
            if setup_result['success']:
                current_app.logger.info(f"✅ Complete SignalWire setup for user {user_id}")
                return True, "Subscription and SignalWire setup completed successfully"
            else:
                current_app.logger.error(f"❌ SignalWire setup failed: {setup_result['error']}")
                return False, setup_result['error']
            
        except Exception as e:
            current_app.logger.error(f"Subscription creation failed: {e}")
            return False, str(e)
