# app/services/usage_tracker.py



import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from sqlalchemy import func, and_, or_
from app.extensions import db
from app.models.subscription import Subscription
from app.models.usage import Usage, UsageOverage
from app.models.message import Message
from app.models.profile import Profile
from app.models.billing_settings import BillingSettings
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)

class UsageTracker:
    """Service for tracking and managing subscription usage"""
    
    @classmethod
    def initialize_usage_for_subscription(cls, subscription_id: str) -> Usage:
        """Initialize usage tracking for a new subscription"""
        try:
            subscription = Subscription.query.get(subscription_id)
            if not subscription:
                raise ValueError(f"Subscription {subscription_id} not found")
            
            # Get plan features
            plan_features = subscription.plan.features
            
            # Calculate period dates
            period_start = subscription.current_period_start
            period_end = subscription.current_period_end
            
            # Create usage record
            usage = Usage(
                user_id=subscription.user_id,
                subscription_id=subscription_id,
                period_start=period_start,
                period_end=period_end,
                sms_credits_remaining=plan_features.get('sms_credits_monthly', 0),
                ai_credits_remaining=plan_features.get('ai_responses_monthly', 0),
                storage_limit_gb=plan_features.get('storage_gb', 0),
                api_calls_limit=plan_features.get('api_calls_monthly', 10000),
                active_profiles=0,
                total_conversations=0
            )
            
            db.session.add(usage)
            db.session.commit()
            
            logger.info(f"Initialized usage tracking for subscription {subscription_id}")
            return usage
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error initializing usage for subscription {subscription_id}: {str(e)}")
            raise
    
    @classmethod
    def track_sms_sent(cls, user_id: str, phone_number: str, message_content: str) -> Dict[str, Any]:
        """Track SMS sent usage"""
        try:
            # Get current subscription and usage
            subscription = cls._get_active_subscription(user_id)
            if not subscription:
                return {'success': False, 'error': 'No active subscription'}
            
            usage = cls._get_current_usage(subscription.id)
            if not usage:
                return {'success': False, 'error': 'Usage tracking not initialized'}
            
            # Calculate SMS credits needed (basic calculation)
            credits_needed = cls._calculate_sms_credits(message_content)
            
            # Check if user has enough credits
            if usage.sms_credits_remaining < credits_needed:
                # Check if overages are allowed
                if cls._are_overages_allowed(subscription):
                    # Create overage record
                    overage_cost = cls._calculate_overage_cost('sms_credits', credits_needed - usage.sms_credits_remaining)
                    cls._create_overage_record(usage.id, 'sms_credits', credits_needed - usage.sms_credits_remaining, overage_cost)
                    
                    # Send overage notification
                    cls._send_usage_notification(user_id, 'sms_overage', {
                        'credits_used': credits_needed,
                        'credits_available': usage.sms_credits_remaining,
                        'overage_cost': overage_cost
                    })
                else:
                    return {'success': False, 'error': 'SMS credit limit exceeded'}
            
            # Update usage
            usage.sms_sent += 1
            usage.sms_credits_used += credits_needed
            usage.sms_credits_remaining = max(0, usage.sms_credits_remaining - credits_needed)
            usage.last_updated = datetime.utcnow()
            
            db.session.commit()
            
            # Check for usage alerts
            cls._check_usage_alerts(user_id, usage)
            
            return {
                'success': True,
                'credits_used': credits_needed,
                'credits_remaining': usage.sms_credits_remaining,
                'overage': usage.sms_credits_remaining == 0
            }
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error tracking SMS sent for user {user_id}: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @classmethod
    def track_sms_received(cls, user_id: str, phone_number: str) -> Dict[str, Any]:
        """Track SMS received (usually doesn't count against limits)"""
        try:
            subscription = cls._get_active_subscription(user_id)
            if not subscription:
                return {'success': False, 'error': 'No active subscription'}
            
            usage = cls._get_current_usage(subscription.id)
            if not usage:
                return {'success': False, 'error': 'Usage tracking not initialized'}
            
            # Update usage
            usage.sms_received += 1
            usage.last_updated = datetime.utcnow()
            
            db.session.commit()
            
            return {'success': True, 'sms_received': usage.sms_received}
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error tracking SMS received for user {user_id}: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @classmethod
    def track_ai_response_generated(cls, user_id: str, profile_id: str, prompt_tokens: int, response_tokens: int) -> Dict[str, Any]:
        """Track AI response generation"""
        try:
            subscription = cls._get_active_subscription(user_id)
            if not subscription:
                return {'success': False, 'error': 'No active subscription'}
            
            usage = cls._get_current_usage(subscription.id)
            if not usage:
                return {'success': False, 'error': 'Usage tracking not initialized'}
            
            # Calculate AI credits needed based on tokens
            credits_needed = cls._calculate_ai_credits(prompt_tokens, response_tokens)
            
            # Check if user has enough credits
            if usage.ai_credits_remaining < credits_needed:
                # Check if overages are allowed
                if cls._are_overages_allowed(subscription):
                    overage_cost = cls._calculate_overage_cost('ai_credits', credits_needed - usage.ai_credits_remaining)
                    cls._create_overage_record(usage.id, 'ai_credits', credits_needed - usage.ai_credits_remaining, overage_cost)
                    
                    cls._send_usage_notification(user_id, 'ai_overage', {
                        'credits_used': credits_needed,
                        'credits_available': usage.ai_credits_remaining,
                        'overage_cost': overage_cost
                    })
                else:
                    return {'success': False, 'error': 'AI credit limit exceeded'}
            
            # Update usage
            usage.ai_responses_generated += 1
            usage.ai_credits_used += credits_needed
            usage.ai_credits_remaining = max(0, usage.ai_credits_remaining - credits_needed)
            usage.last_updated = datetime.utcnow()
            
            db.session.commit()
            
            # Check for usage alerts
            cls._check_usage_alerts(user_id, usage)
            
            return {
                'success': True,
                'credits_used': credits_needed,
                'credits_remaining': usage.ai_credits_remaining,
                'overage': usage.ai_credits_remaining == 0
            }
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error tracking AI response for user {user_id}: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @classmethod
    def track_storage_usage(cls, user_id: str, additional_gb: float) -> Dict[str, Any]:
        """Track storage usage"""
        try:
            subscription = cls._get_active_subscription(user_id)
            if not subscription:
                return {'success': False, 'error': 'No active subscription'}
            
            usage = cls._get_current_usage(subscription.id)
            if not usage:
                return {'success': False, 'error': 'Usage tracking not initialized'}
            
            # Check if storage limit would be exceeded
            new_storage_total = usage.storage_used_gb + additional_gb
            if new_storage_total > usage.storage_limit_gb:
                if not cls._are_overages_allowed(subscription):
                    return {'success': False, 'error': 'Storage limit exceeded'}
                
                # Create overage record for excess storage
                overage_gb = new_storage_total - usage.storage_limit_gb
                overage_cost = cls._calculate_overage_cost('storage_gb', overage_gb)
                cls._create_overage_record(usage.id, 'storage_gb', overage_gb, overage_cost)
            
            # Update usage
            usage.storage_used_gb += additional_gb
            usage.last_updated = datetime.utcnow()
            
            db.session.commit()
            
            # Check for usage alerts
            cls._check_usage_alerts(user_id, usage)
            
            return {
                'success': True,
                'storage_used': float(usage.storage_used_gb),
                'storage_limit': float(usage.storage_limit_gb),
                'percentage_used': (float(usage.storage_used_gb) / float(usage.storage_limit_gb)) * 100
            }
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error tracking storage usage for user {user_id}: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @classmethod
    def track_api_call(cls, user_id: str, endpoint: str, method: str) -> Dict[str, Any]:
        """Track API call usage"""
        try:
            subscription = cls._get_active_subscription(user_id)
            if not subscription:
                return {'success': False, 'error': 'No active subscription'}
            
            usage = cls._get_current_usage(subscription.id)
            if not usage:
                return {'success': False, 'error': 'Usage tracking not initialized'}
            
            # Check API call limit
            if usage.api_calls_made >= usage.api_calls_limit:
                if not cls._are_overages_allowed(subscription):
                    return {'success': False, 'error': 'API call limit exceeded'}
                
                # Create overage record
                overage_cost = cls._calculate_overage_cost('api_calls', 1)
                cls._create_overage_record(usage.id, 'api_calls', 1, overage_cost)
            
            # Update usage
            usage.api_calls_made += 1
            usage.last_updated = datetime.utcnow()
            
            db.session.commit()
            
            return {
                'success': True,
                'api_calls_made': usage.api_calls_made,
                'api_calls_limit': usage.api_calls_limit,
                'calls_remaining': max(0, usage.api_calls_limit - usage.api_calls_made)
            }
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error tracking API call for user {user_id}: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @classmethod
    def update_active_profiles_count(cls, user_id: str) -> Dict[str, Any]:
        """Update count of active profiles"""
        try:
            subscription = cls._get_active_subscription(user_id)
            if not subscription:
                return {'success': False, 'error': 'No active subscription'}
            
            usage = cls._get_current_usage(subscription.id)
            if not usage:
                return {'success': False, 'error': 'Usage tracking not initialized'}
            
            # Count active profiles
            active_profiles = Profile.query.filter_by(user_id=user_id, is_active=True).count()
            
            # Check profile limit
            plan_features = subscription.plan.features
            max_profiles = plan_features.get('max_profiles', 1)
            
            if active_profiles > max_profiles:
                return {'success': False, 'error': f'Profile limit exceeded. Maximum: {max_profiles}'}
            
            # Update usage
            usage.active_profiles = active_profiles
            usage.last_updated = datetime.utcnow()
            
            db.session.commit()
            
            return {
                'success': True,
                'active_profiles': active_profiles,
                'max_profiles': max_profiles,
                'profiles_remaining': max_profiles - active_profiles
            }
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error updating profile count for user {user_id}: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @classmethod
    def get_usage_history(cls, subscription_id: str, start_date: str, end_date: str, granularity: str = 'day') -> List[Dict[str, Any]]:
        """Get usage history for analytics"""
        try:
            start_dt = datetime.fromisoformat(start_date)
            end_dt = datetime.fromisoformat(end_date)
            
            # Determine grouping based on granularity
            if granularity == 'day':
                date_trunc = func.date_trunc('day', Usage.created_at)
            elif granularity == 'week':
                date_trunc = func.date_trunc('week', Usage.created_at)
            elif granularity == 'month':
                date_trunc = func.date_trunc('month', Usage.created_at)
            else:
                date_trunc = func.date_trunc('day', Usage.created_at)
            
            # Query usage data
            results = db.session.query(
                date_trunc.label('date'),
                func.max(Usage.sms_sent).label('sms_sent'),
                func.max(Usage.sms_received).label('sms_received'),
                func.max(Usage.ai_responses_generated).label('ai_responses'),
                func.max(Usage.api_calls_made).label('api_calls'),
                func.max(Usage.active_profiles).label('active_profiles'),
                func.max(Usage.total_conversations).label('total_conversations'),
                func.max(Usage.storage_used_gb).label('storage_used_gb')
            ).filter(
                Usage.subscription_id == subscription_id,
                Usage.created_at >= start_dt,
                Usage.created_at <= end_dt
            ).group_by(date_trunc).order_by(date_trunc).all()
            
            # Format results
            usage_history = []
            for result in results:
                usage_history.append({
                    'date': result.date.isoformat(),
                    'sms_sent': result.sms_sent or 0,
                    'sms_received': result.sms_received or 0,
                    'ai_responses': result.ai_responses or 0,
                    'api_calls': result.api_calls or 0,
                    'active_profiles': result.active_profiles or 0,
                    'total_conversations': result.total_conversations or 0,
                    'storage_used_gb': float(result.storage_used_gb) if result.storage_used_gb else 0.0
                })
            
            return usage_history
            
        except Exception as e:
            logger.error(f"Error getting usage history for subscription {subscription_id}: {str(e)}")
            return []
    
    @classmethod
    def reset_usage_for_new_period(cls, subscription_id: str) -> Dict[str, Any]:
        """Reset usage tracking for a new billing period"""
        try:
            subscription = Subscription.query.get(subscription_id)
            if not subscription:
                return {'success': False, 'error': 'Subscription not found'}
            
            # Get plan features for new limits
            plan_features = subscription.plan.features
            
            # Create new usage record for the new period
            new_usage = Usage(
                user_id=subscription.user_id,
                subscription_id=subscription_id,
                period_start=subscription.current_period_start,
                period_end=subscription.current_period_end,
                sms_credits_remaining=plan_features.get('sms_credits_monthly', 0),
                ai_credits_remaining=plan_features.get('ai_responses_monthly', 0),
                storage_limit_gb=plan_features.get('storage_gb', 0),
                api_calls_limit=plan_features.get('api_calls_monthly', 10000),
                # Keep current counts that don't reset
                active_profiles=0,  # Will be updated on next profile check
                total_conversations=0  # Will be calculated from current period
            )
            
            db.session.add(new_usage)
            db.session.commit()
            
            logger.info(f"Reset usage tracking for subscription {subscription_id} new period")
            return {'success': True, 'message': 'Usage reset for new period'}
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error resetting usage for subscription {subscription_id}: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    # Private helper methods
    
    @classmethod
    def _get_active_subscription(cls, user_id: str) -> Optional[Subscription]:
        """Get user's active subscription"""
        return Subscription.query.filter_by(
            user_id=user_id,
            status='active'
        ).first()
    
    @classmethod
    def _get_current_usage(cls, subscription_id: str) -> Optional[Usage]:
        """Get current usage record for subscription"""
        return Usage.query.filter(
            Usage.subscription_id == subscription_id,
            Usage.period_start <= datetime.utcnow(),
            Usage.period_end >= datetime.utcnow()
        ).first()
    
    @classmethod
    def _calculate_sms_credits(cls, message_content: str) -> int:
        """Calculate SMS credits needed based on message content"""
        # Basic calculation: 1 credit per 160 characters (SMS segment)
        message_length = len(message_content)
        segments = (message_length // 160) + (1 if message_length % 160 > 0 else 0)
        return max(1, segments)  # Minimum 1 credit
    
    @classmethod
    def _calculate_ai_credits(cls, prompt_tokens: int, response_tokens: int) -> int:
        """Calculate AI credits needed based on token usage"""
        # Basic calculation: 1 credit per 1000 tokens
        total_tokens = prompt_tokens + response_tokens
        credits = (total_tokens // 1000) + (1 if total_tokens % 1000 > 0 else 0)
        return max(1, credits)  # Minimum 1 credit
    
    @classmethod
    def _are_overages_allowed(cls, subscription: Subscription) -> bool:
        """Check if overages are allowed for this subscription"""
        # Check plan features or subscription settings
        plan_features = subscription.plan.features
        return plan_features.get('allow_overages', False)
    
    @classmethod
    def _calculate_overage_cost(cls, metric: str, overage_amount: float) -> float:
        """Calculate cost for overage usage"""
        # Define overage rates
        overage_rates = {
            'sms_credits': 0.02,      # $0.02 per SMS credit
            'ai_credits': 0.05,       # $0.05 per AI credit
            'storage_gb': 1.0,        # $1.00 per GB
            'api_calls': 0.001        # $0.001 per API call
        }
        
        rate = overage_rates.get(metric, 0.0)
        return overage_amount * rate
    
    @classmethod
    def _create_overage_record(cls, usage_id: str, metric: str, overage_amount: float, overage_cost: float):
        """Create overage record"""
        overage = UsageOverage(
            usage_id=usage_id,
            metric=metric,
            overage_amount=int(overage_amount),
            overage_cost=overage_cost,
            rate_per_unit=overage_cost / overage_amount if overage_amount > 0 else 0
        )
        
        db.session.add(overage)
    
    @classmethod
    def _check_usage_alerts(cls, user_id: str, usage: Usage):
        """Check if usage alerts should be sent"""
        try:
            # Get billing settings for alert thresholds
            billing_settings = BillingSettings.query.filter_by(user_id=user_id).first()
            if not billing_settings or not billing_settings.notifications.get('usage_alerts', True):
                return
            
            thresholds = billing_settings.usage_alert_thresholds
            
            # Check SMS credits
            sms_total = usage.sms_credits_used + usage.sms_credits_remaining
            if sms_total > 0:
                sms_percentage = (usage.sms_credits_used / sms_total) * 100
                if sms_percentage >= thresholds.get('sms_credits', 80):
                    cls._send_usage_notification(user_id, 'sms_limit_warning', {
                        'percentage_used': sms_percentage,
                        'credits_remaining': usage.sms_credits_remaining
                    })
            
            # Check AI credits
            ai_total = usage.ai_credits_used + usage.ai_credits_remaining
            if ai_total > 0:
                ai_percentage = (usage.ai_credits_used / ai_total) * 100
                if ai_percentage >= thresholds.get('ai_credits', 80):
                    cls._send_usage_notification(user_id, 'ai_limit_warning', {
                        'percentage_used': ai_percentage,
                        'credits_remaining': usage.ai_credits_remaining
                    })
            
            # Check storage
            if usage.storage_limit_gb > 0:
                storage_percentage = (float(usage.storage_used_gb) / float(usage.storage_limit_gb)) * 100
                if storage_percentage >= thresholds.get('storage', 80):
                    cls._send_usage_notification(user_id, 'storage_limit_warning', {
                        'percentage_used': storage_percentage,
                        'storage_remaining': float(usage.storage_limit_gb - usage.storage_used_gb)
                    })
            
        except Exception as e:
            logger.error(f"Error checking usage alerts for user {user_id}: {str(e)}")
    
    @classmethod
    def _send_usage_notification(cls, user_id: str, notification_type: str, data: Dict[str, Any]):
        """Send usage notification to user"""
        try:
            # Use notification service to send alerts
            NotificationService.send_usage_alert(user_id, notification_type, data)
        except Exception as e:
            logger.error(f"Error sending usage notification: {str(e)}")


# Usage tracking middleware for automatic tracking
class UsageTrackingMiddleware:
    """Middleware to automatically track certain usage events"""
    
    def __init__(self, app=None):
        self.app = app
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize the middleware with Flask app"""
        app.before_request(self.before_request)
        app.after_request(self.after_request)
    
    def before_request(self):
        """Track API calls before request processing"""
        from flask import request, g
        
        if request.endpoint and request.endpoint.startswith('api.'):
            # Get user ID from JWT token
            try:
                from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request
                verify_jwt_in_request()
                user_id = get_jwt_identity()
                
                if user_id:
                    # Track the API call
                    result = UsageTracker.track_api_call(user_id, request.endpoint, request.method)
                    
                    # Store result in g for potential use in the request
                    g.usage_tracking_result = result
                    
                    # If API limit exceeded, you might want to abort the request
                    if not result.get('success') and 'limit exceeded' in result.get('error', ''):
                        from flask import jsonify, abort
                        abort(429)  # Too Many Requests
                        
            except Exception as e:
                # Don't fail the request if usage tracking fails
                logger.warning(f"Usage tracking failed: {str(e)}")
    
    def after_request(self, response):
        """Track successful operations after request"""
        # Could be used to track successful operations
        return response