# app/core/services.py
"""
UNIFIED SERVICE LAYER - CORRECTED VERSION
Consolidates all business logic with Stripe and SignalWire subproject integration
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from sqlalchemy import func, and_, or_
from flask import current_app
from flask_jwt_extended import create_access_token, create_refresh_token
import stripe
import logging

from app.extensions import db
from app.core.models import (
    User, Client, Message, Subscription, SubscriptionPlan, 
    Payment, PaymentMethod, Invoice, UsageRecord, APIKey,
    ActivityLog, NotificationSetting, NotificationLog,
    SignalWireSubproject, SignalWirePhoneNumber, TrialNotification
)
from app.utils.signalwire import SignalWireClient
from app.utils.auth import generate_api_key, hash_api_key
from app.utils.helpers import generate_invoice_number, send_email, send_welcome_email


# Initialize Stripe
stripe.api_key = current_app.config.get('STRIPE_SECRET_KEY') if current_app else None


# =============================================================================
# BASE SERVICE CLASS
# =============================================================================

class BaseService:
    """Base service with common functionality"""
    
    def __init__(self):
        self.db = db
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def _log_activity(self, user_id: int, action: str, resource_type: str = None, 
                     resource_id: str = None, details: str = None, 
                     ip_address: str = None, user_agent: str = None):
        """Log user activity"""
        try:
            log = ActivityLog(
                user_id=user_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                details=details,
                ip_address=ip_address,
                user_agent=user_agent
            )
            self.db.session.add(log)
            self.db.session.commit()
        except Exception as e:
            self.logger.error(f"Failed to log activity: {e}")
    
    def _create_response(self, success: bool, data: Any = None, message: str = None, 
                        error: str = None, code: int = 200) -> Tuple[Dict, int]:
        """Create standardized response"""
        response = {
            'success': success,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        if data is not None:
            response['data'] = data
        if message:
            response['message'] = message
        if error:
            response['error'] = error
        
        return response, code


# =============================================================================
# USER SERVICE WITH STRIPE INTEGRATION
# =============================================================================

class UserService(BaseService):
    """Handles all user-related operations with Stripe integration"""
    
    def register_user(self, data: Dict) -> Tuple[Dict, int]:
        """Register a new user with Stripe customer creation"""
        try:
            # Check if user exists
            existing_user = User.query.filter(
                or_(User.username == data['username'], User.email == data['email'])
            ).first()
            
            if existing_user:
                if existing_user.username == data['username']:
                    return self._create_response(False, error="Username already taken", code=409)
                else:
                    return self._create_response(False, error="Email already registered", code=409)
            
            # Create Stripe customer first
            try:
                stripe_customer = stripe.Customer.create(
                    email=data['email'],
                    name=f"{data.get('first_name', '')} {data.get('last_name', '')}".strip(),
                    metadata={
                        'username': data['username'],
                        'source': 'assistext_registration'
                    }
                )
                self.logger.info(f"Created Stripe customer: {stripe_customer.id}")
            except stripe.error.StripeError as e:
                self.logger.error(f"Stripe customer creation failed: {e}")
                return self._create_response(False, error="Payment system setup failed", code=500)
            
            # Create new user
            user = User(
                username=data['username'],
                email=data['email'],
                first_name=data.get('first_name'),
                last_name=data.get('last_name'),
                personal_phone=data.get('personal_phone'),
                timezone=data.get('timezone', 'UTC'),
                preferred_country=data.get('preferred_country', 'US'),
                preferred_region=data.get('preferred_region'),
                preferred_city=data.get('preferred_city'),
                preferred_area_code=data.get('preferred_area_code'),
                trial_status='pending_payment',
                stripe_customer_id=stripe_customer.id
            )
            user.set_password(data['password'])
            
            self.db.session.add(user)
            self.db.session.commit()
            
            # Generate tokens
            tokens = user.generate_tokens()
            
            # Send welcome email
            send_welcome_email(user.to_dict())
            
            # Log activity
            self._log_activity(user.id, 'user_registered')
            
            return self._create_response(
                True, 
                data={
                    'user': user.to_dict(),
                    'access_token': tokens['access_token'],
                    'refresh_token': tokens['refresh_token'],
                    'stripe_customer_id': user.stripe_customer_id
                },
                message="User registered successfully",
                code=201
            )
            
        except Exception as e:
            self.db.session.rollback()
            self.logger.error(f"Registration error: {e}")
            return self._create_response(False, error="Registration failed", code=500)
    
    def authenticate_user(self, email_or_username: str, password: str) -> Tuple[Dict, int]:
        """Authenticate user login"""
        try:
            # Find user by email or username
            user = User.query.filter(
                or_(User.email == email_or_username, User.username == email_or_username)
            ).first()
            
            if not user or not user.check_password(password):
                return self._create_response(False, error="Invalid credentials", code=401)
            
            if not user.is_active:
                return self._create_response(False, error="Account deactivated", code=401)
            
            # Update last login
            user.last_login = datetime.utcnow()
            self.db.session.commit()
            
            # Generate tokens
            tokens = user.generate_tokens()
            
            # Log activity
            self._log_activity(user.id, 'user_login')
            
            return self._create_response(
                True,
                data={
                    'user': user.to_dict(),
                    'access_token': tokens['access_token'],
                    'refresh_token': tokens['refresh_token']
                },
                message="Login successful"
            )
            
        except Exception as e:
            self.logger.error(f"Authentication error: {e}")
            return self._create_response(False, error="Authentication failed", code=500)
    
    def get_user_profile(self, user_id: int) -> Tuple[Dict, int]:
        """Get user profile"""
        try:
            user = User.query.get(user_id)
            if not user:
                return self._create_response(False, error="User not found", code=404)
            
            return self._create_response(True, data=user.to_dict())
            
        except Exception as e:
            self.logger.error(f"Get profile error: {e}")
            return self._create_response(False, error="Failed to get profile", code=500)


# =============================================================================
# SIGNALWIRE SUBPROJECT SERVICE
# =============================================================================

class SignalWireService(BaseService):
    """Handles SignalWire subproject and phone number management"""
    
    def __init__(self):
        super().__init__()
        self.signalwire = SignalWireClient()
    
    def create_subproject_for_user(self, user_id: int) -> Tuple[Dict, int]:
        """Create SignalWire subproject for user"""
        try:
            user = User.query.get(user_id)
            if not user:
                return self._create_response(False, error="User not found", code=404)
            
            # Check if subproject already exists
            existing_subproject = SignalWireSubproject.query.filter_by(user_id=user_id).first()
            if existing_subproject:
                return self._create_response(
                    True, 
                    data=existing_subproject.to_dict(),
                    message="Subproject already exists"
                )
            
            # Generate friendly name: username_userid
            friendly_name = f"{user.username}_{user.id}"
            
            # Create subproject in SignalWire
            subproject_result = self.signalwire.create_subproject(friendly_name)
            
            if not subproject_result['success']:
                return self._create_response(False, error=subproject_result['error'], code=400)
            
            # Create local record
            subproject = SignalWireSubproject(
                user_id=user_id,
                subproject_sid=subproject_result['data']['sid'],
                friendly_name=friendly_name,
                auth_token=subproject_result['data'].get('auth_token'),
                status='active',
                trial_active=True,
                trial_expires_at=datetime.utcnow() + timedelta(days=14)
            )
            
            self.db.session.add(subproject)
            
            # Update user record
            user.signalwire_subproject_sid = subproject.subproject_sid
            user.signalwire_friendly_name = friendly_name
            
            self.db.session.commit()
            
            # Log activity
            self._log_activity(user_id, 'signalwire_subproject_created', 'subproject', subproject.subproject_sid)
            
            return self._create_response(
                True,
                data=subproject.to_dict(),
                message="SignalWire subproject created successfully",
                code=201
            )
            
        except Exception as e:
            self.db.session.rollback()
            self.logger.error(f"Create subproject error: {e}")
            return self._create_response(False, error="Failed to create subproject", code=500)
    
    def purchase_phone_number_for_user(self, user_id: int, phone_number: str, 
                                     area_code: str = None) -> Tuple[Dict, int]:
        """Purchase phone number and attach to user's subproject"""
        try:
            user = User.query.get(user_id)
            if not user:
                return self._create_response(False, error="User not found", code=404)
            
            # Get or create subproject
            subproject = SignalWireSubproject.query.filter_by(user_id=user_id).first()
            if not subproject:
                subproject_result = self.create_subproject_for_user(user_id)
                if not subproject_result[0]['success']:
                    return subproject_result
                subproject = SignalWireSubproject.query.filter_by(user_id=user_id).first()
            
            # Purchase phone number
            webhook_url = f"{current_app.config.get('BACKEND_URL', 'https://backend.assitext.ca')}/api/webhooks/sms/{user_id}"
            
            purchase_result = self.signalwire.purchase_phone_number(
                phone_number=phone_number,
                subproject_sid=subproject.subproject_sid,
                sms_webhook_url=webhook_url
            )
            
            if not purchase_result['success']:
                return self._create_response(False, error=purchase_result['error'], code=400)
            
            # Create local phone number record
            phone_record = SignalWirePhoneNumber(
                subproject_id=subproject.id,
                user_id=user_id,
                phone_number=phone_number,
                phone_number_sid=purchase_result['data']['sid'],
                friendly_name=f"{user.username}_phone",
                sms_webhook_url=webhook_url,
                status='active'
            )
            
            self.db.session.add(phone_record)
            
            # Update user record
            user.selected_phone_number = phone_number
            user.signalwire_phone_sid = phone_record.phone_number_sid
            user.trial_signalwire_setup = True
            
            self.db.session.commit()
            
            # Log activity
            self._log_activity(user_id, 'phone_number_purchased', 'phone_number', phone_number)
            
            return self._create_response(
                True,
                data={
                    'phone_number': phone_number,
                    'phone_number_sid': phone_record.phone_number_sid,
                    'subproject_sid': subproject.subproject_sid,
                    'webhook_url': webhook_url
                },
                message="Phone number purchased successfully"
            )
            
        except Exception as e:
            self.db.session.rollback()
            self.logger.error(f"Purchase phone number error: {e}")
            return self._create_response(False, error="Failed to purchase phone number", code=500)
    
    def suspend_user_subproject(self, user_id: int, reason: str = 'trial_expired') -> Tuple[Dict, int]:
        """Suspend user's SignalWire subproject (for trial expiry or non-payment)"""
        try:
            subproject = SignalWireSubproject.query.filter_by(user_id=user_id).first()
            if not subproject:
                return self._create_response(False, error="Subproject not found", code=404)
            
            # Suspend phone numbers by removing webhooks
            phone_numbers = SignalWirePhoneNumber.query.filter_by(subproject_id=subproject.id).all()
            
            for phone in phone_numbers:
                # Remove webhook configuration
                webhook_result = self.signalwire.remove_webhooks_from_number(phone.phone_number_sid)
                if webhook_result['success']:
                    phone.status = 'suspended'
                    phone.sms_webhook_url = None
                    phone.voice_webhook_url = None
            
            # Update subproject status
            subproject.status = 'suspended'
            if reason == 'trial_expired':
                subproject.trial_active = False
            elif reason == 'payment_failed':
                subproject.suspended_for_payment = True
            
            self.db.session.commit()
            
            # Log activity
            self._log_activity(user_id, 'subproject_suspended', 'subproject', subproject.subproject_sid, reason)
            
            return self._create_response(
                True,
                data={'subproject_sid': subproject.subproject_sid, 'reason': reason},
                message="Subproject suspended successfully"
            )
            
        except Exception as e:
            self.db.session.rollback()
            self.logger.error(f"Suspend subproject error: {e}")
            return self._create_response(False, error="Failed to suspend subproject", code=500)
    
    def reactivate_user_subproject(self, user_id: int) -> Tuple[Dict, int]:
        """Reactivate user's SignalWire subproject (after subscription payment)"""
        try:
            subproject = SignalWireSubproject.query.filter_by(user_id=user_id).first()
            if not subproject:
                return self._create_response(False, error="Subproject not found", code=404)
            
            # Reactivate phone numbers by restoring webhooks
            phone_numbers = SignalWirePhoneNumber.query.filter_by(subproject_id=subproject.id).all()
            
            for phone in phone_numbers:
                webhook_url = f"{current_app.config.get('BACKEND_URL')}/api/webhooks/sms/{user_id}"
                
                # Restore webhook configuration
                webhook_result = self.signalwire.configure_webhooks(
                    phone.phone_number_sid,
                    sms_url=webhook_url
                )
                
                if webhook_result['success']:
                    phone.status = 'active'
                    phone.sms_webhook_url = webhook_url
            
            # Update subproject status
            subproject.status = 'active'
            subproject.suspended_for_payment = False
            
            self.db.session.commit()
            
            # Log activity
            self._log_activity(user_id, 'subproject_reactivated', 'subproject', subproject.subproject_sid)
            
            return self._create_response(
                True,
                data={'subproject_sid': subproject.subproject_sid},
                message="Subproject reactivated successfully"
            )
            
        except Exception as e:
            self.db.session.rollback()
            self.logger.error(f"Reactivate subproject error: {e}")
            return self._create_response(False, error="Failed to reactivate subproject", code=500)


# =============================================================================
# STRIPE BILLING SERVICE
# =============================================================================

class BillingService(BaseService):
    """Handles billing, subscriptions, and payments with Stripe"""
    
    def start_trial_with_payment_method(self, user_id: int, payment_method_id: str, 
                                      preferred_area_code: str = '416') -> Tuple[Dict, int]:
        """Start trial with payment method validation"""
        try:
            user = User.query.get(user_id)
            if not user:
                return self._create_response(False, error="User not found", code=404)
            
            if not user.is_trial_eligible:
                return self._create_response(False, error="Not eligible for trial", code=400)
            
            # Validate and attach payment method to Stripe customer
            try:
                stripe.PaymentMethod.attach(
                    payment_method_id,
                    customer=user.stripe_customer_id
                )
                
                # Set as default payment method
                stripe.Customer.modify(
                    user.stripe_customer_id,
                    invoice_settings={'default_payment_method': payment_method_id}
                )
                
                # Store payment method locally
                payment_method_details = stripe.PaymentMethod.retrieve(payment_method_id)
                
                payment_method = PaymentMethod(
                    user_id=user_id,
                    payment_type='card',
                    last_four=payment_method_details.card.last4,
                    brand=payment_method_details.card.brand,
                    exp_month=payment_method_details.card.exp_month,
                    exp_year=payment_method_details.card.exp_year,
                    is_default=True,
                    stripe_payment_method_id=payment_method_id
                )
                
                self.db.session.add(payment_method)
                
            except stripe.error.StripeError as e:
                self.logger.error(f"Payment method validation failed: {e}")
                return self._create_response(False, error="Invalid payment method", code=400)
            
            # Create SignalWire subproject and phone number
            signalwire_service = get_signalwire_service()
            
            # Create subproject
            subproject_result = signalwire_service.create_subproject_for_user(user_id)
            if not subproject_result[0]['success']:
                return subproject_result
            
            # Search for available phone numbers
            numbers_result = self.signalwire.search_phone_numbers(area_code=preferred_area_code)
            if not numbers_result['success'] or not numbers_result['data']:
                return self._create_response(False, error="No phone numbers available", code=400)
            
            # Purchase first available number
            selected_number = numbers_result['data'][0]['phone_number']
            phone_result = signalwire_service.purchase_phone_number_for_user(user_id, selected_number)
            
            if not phone_result[0]['success']:
                return phone_result
            
            # Update user trial status
            user.trial_status = 'active'
            user.trial_started_at = datetime.utcnow()
            user.trial_expires_at = datetime.utcnow() + timedelta(days=14)
            user.payment_validated_at = datetime.utcnow()
            
            self.db.session.commit()
            
            # Log activity
            self._log_activity(user_id, 'trial_started')
            
            return self._create_response(
                True,
                data={
                    'trial_expires_at': user.trial_expires_at.isoformat(),
                    'phone_number': user.selected_phone_number,
                    'subproject_sid': user.signalwire_subproject_sid,
                    'payment_method_added': True
                },
                message="Trial started successfully"
            )
            
        except Exception as e:
            self.db.session.rollback()
            self.logger.error(f"Start trial error: {e}")
            return self._create_response(False, error="Failed to start trial", code=500)
    
    def create_subscription(self, user_id: int, plan_id: int, billing_cycle: str = 'monthly') -> Tuple[Dict, int]:
        """Create paid subscription with Stripe"""
        try:
            user = User.query.get(user_id)
            plan = SubscriptionPlan.query.get(plan_id)
            
            if not user or not plan:
                return self._create_response(False, error="User or plan not found", code=404)
            
            # Get Stripe price ID based on billing cycle
            if billing_cycle == 'monthly':
                stripe_price_id = plan.stripe_price_id_monthly
            elif billing_cycle == 'annual':
                stripe_price_id = plan.stripe_price_id_annual
            else:
                return self._create_response(False, error="Invalid billing cycle", code=400)
            
            if not stripe_price_id:
                return self._create_response(False, error="Plan not configured for this billing cycle", code=400)
            
            # Create Stripe subscription
            try:
                stripe_subscription = stripe.Subscription.create(
                    customer=user.stripe_customer_id,
                    items=[{'price': stripe_price_id}],
                    metadata={
                        'user_id': str(user_id),
                        'plan_id': str(plan_id)
                    }
                )
            except stripe.error.StripeError as e:
                self.logger.error(f"Stripe subscription creation failed: {e}")
                return self._create_response(False, error="Subscription creation failed", code=400)
            
            # Create local subscription record
            subscription = Subscription(
                user_id=user_id,
                plan_id=plan_id,
                status=stripe_subscription.status,
                billing_cycle=billing_cycle,
                current_period_start=datetime.fromtimestamp(stripe_subscription.current_period_start),
                current_period_end=datetime.fromtimestamp(stripe_subscription.current_period_end),
                amount=plan.monthly_price if billing_cycle == 'monthly' else plan.annual_price,
                stripe_subscription_id=stripe_subscription.id,
                stripe_customer_id=user.stripe_customer_id
            )
            
            self.db.session.add(subscription)
            
            # Update user status
            user.trial_status = 'converted'
            
            # Update user limits based on plan
            user.daily_ai_response_limit = plan.ai_response_limit_daily
            
            # Reactivate SignalWire subproject if it was suspended
            signalwire_service = get_signalwire_service()
            signalwire_service.reactivate_user_subproject(user_id)
            
            self.db.session.commit()
            
            # Log activity
            self._log_activity(user_id, 'subscription_created', 'subscription', str(subscription.id))
            
            return self._create_response(
                True,
                data=subscription.to_dict(),
                message="Subscription created successfully"
            )
            
        except Exception as e:
            self.db.session.rollback()
            self.logger.error(f"Create subscription error: {e}")
            return self._create_response(False, error="Failed to create subscription", code=500)
    
    def get_usage_statistics(self, user_id: int, billing_period: str = None) -> Tuple[Dict, int]:
        """Get user usage statistics"""
        try:
            if not billing_period:
                billing_period = datetime.utcnow().strftime('%Y-%m')
            
            usage_stats = self.db.session.query(
                UsageRecord.usage_type,
                func.sum(UsageRecord.quantity).label('total_quantity'),
                func.sum(UsageRecord.cost).label('total_cost')
            ).filter(
                and_(
                    UsageRecord.user_id == user_id,
                    UsageRecord.billing_period == billing_period
                )
            ).group_by(UsageRecord.usage_type).all()
            
            stats_dict = {}
            for stat in usage_stats:
                stats_dict[stat.usage_type] = {
                    'quantity': int(stat.total_quantity or 0),
                    'cost': float(stat.total_cost or 0)
                }
            
            return self._create_response(True, data=stats_dict)
            
        except Exception as e:
            self.logger.error(f"Get usage statistics error: {e}")
            return self._create_response(False, error="Failed to get usage stats", code=500)


# =============================================================================
# MESSAGING SERVICE WITH SUBPROJECT INTEGRATION
# =============================================================================

class MessagingService(BaseService):
    """Handles SMS and messaging operations with subproject tracking"""
    
    def __init__(self):
        super().__init__()
        self.signalwire = SignalWireClient()
    
    def send_message(self, user_id: int, to_number: str, body: str, 
                    client_id: int = None, ai_generated: bool = False) -> Tuple[Dict, int]:
        """Send SMS message via user's subproject"""
        try:
            user = User.query.get(user_id)
            if not user or not user.selected_phone_number:
                return self._create_response(False, error="User phone number not configured", code=400)
            
            # Check usage limits
            usage_check = self._check_usage_limits(user, 'sms_sent')
            if not usage_check['allowed']:
                return self._create_response(False, error=usage_check['error'], code=429)
            
            # Send via SignalWire using subproject
            result = self.signalwire.send_message_via_subproject(
                subproject_sid=user.signalwire_subproject_sid,
                from_number=user.selected_phone_number,
                to_number=to_number,
                body=body
            )
            
            if not result['success']:
                return self._create_response(False, error=result['error'], code=400)
            
            # Save message to database
            message = Message(
                user_id=user_id,
                client_id=client_id,
                from_number=user.selected_phone_number,
                to_number=to_number,
                body=body,
                direction='outbound',
                signalwire_sid=result['data']['sid'],
                signalwire_subproject_sid=user.signalwire_subproject_sid,
                status='sent',
                ai_generated=ai_generated,
                sent_at=datetime.utcnow()
            )
            
            self.db.session.add(message)
            
            # Record usage
            self._record_usage(user_id, 'sms_sent', 1, result['data'].get('cost'))
            
            self.db.session.commit()
            
            return self._create_response(
                True, 
                data=message.to_dict(), 
                message="Message sent successfully"
            )
            
        except Exception as e:
            self.db.session.rollback()
            self.logger.error(f"Send message error: {e}")
            return self._create_response(False, error="Failed to send message", code=500)
    
    def process_incoming_message(self, from_number: str, to_number: str, 
                               body: str, signalwire_sid: str) -> Tuple[Dict, int]:
        """Process incoming SMS message"""
        try:
            # Find user by phone number
            user = User.query.filter_by(selected_phone_number=to_number).first()
            if not user:
                self.logger.warning(f"No user found for phone number: {to_number}")
                return self._create_response(False, error="User not found")
            
            # Check if user's service is active
            if user.trial_status == 'expired' and not self._has_active_subscription(user):
                self.logger.warning(f"Incoming message for inactive user: {user.id}")
                return self._create_response(False, error="User service inactive")
            
            # Find or create client
            client = Client.query.filter_by(
                user_id=user.id, 
                phone_number=from_number
            ).first()
            
            if not client:
                client = Client(
                    user_id=user.id,
                    phone_number=from_number,
                    last_contact=datetime.utcnow()
                )
                self.db.session.add(client)
                self.db.session.flush()
            else:
                client.last_contact = datetime.utcnow()
            
            # Save incoming message
            message = Message(
                user_id=user.id,
                client_id=client.id,
                from_number=from_number,
                to_number=to_number,
                body=body,
                direction='inbound',
                signalwire_sid=signalwire_sid,
                signalwire_subproject_sid=user.signalwire_subproject_sid,
                status='received'
            )
            
            self.db.session.add(message)
            
            # Record usage
            self._record_usage(user.id, 'sms_received', 1)
            
            self.db.session.commit()
            
            # Check if auto-reply should be sent
            if user.auto_reply_enabled and user.ai_enabled:
                self._queue_ai_response(user, client, message)
            
            return self._create_response(
                True, 
                data=message.to_dict(), 
                message="Message processed"
            )
            
        except Exception as e:
            self.db.session.rollback()
            self.logger.error(f"Process incoming message error: {e}")
            return self._create_response(False, error="Failed to process message", code=500)
    
    def _has_active_subscription(self, user: User) -> bool:
        """Check if user has active subscription"""
        active_subscription = Subscription.query.filter_by(
            user_id=user.id,
            status='active'
        ).first()
        return active_subscription is not None
    
    def _check_usage_limits(self, user: User, usage_type: str) -> Dict:
        """Check if user has exceeded usage limits"""
        try:
            # Get current subscription or trial limits
            subscription = Subscription.query.filter_by(
                user_id=user.id, 
                status='active'
            ).first()
            
            if subscription:
                plan = subscription.plan
                if usage_type == 'sms_sent':
                    limit = plan.sms_limit_monthly
                elif usage_type == 'ai_responses':
                    limit = plan.ai_response_limit_daily
                else:
                    limit = 1000  # Default limit
            else:
                # Trial limits
                if usage_type == 'sms_sent':
                    limit = 100
                elif usage_type == 'ai_responses':
                    limit = user.daily_ai_response_limit
                else:
                    limit = 50
            
            # Check current period usage
            if usage_type == 'ai_responses':
                # Daily limit
                if not user.can_make_ai_response():
                    return {'allowed': False, 'error': 'Daily AI response limit exceeded'}
            else:
                # Monthly limit
                current_period_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                usage_count = self.db.session.query(func.sum(UsageRecord.quantity)).filter(
                    and_(
                        UsageRecord.user_id == user.id,
                        UsageRecord.usage_type == usage_type,
                        UsageRecord.created_at >= current_period_start
                    )
                ).scalar() or 0
                
                if usage_count >= limit:
                    return {'allowed': False, 'error': f'{usage_type} limit exceeded'}
            
            return {'allowed': True}
            
        except Exception as e:
            self.logger.error(f"Usage limit check error: {e}")
            return {'allowed': False, 'error': 'Unable to check limits'}
    
    def _record_usage(self, user_id: int, usage_type: str, quantity: int, cost: float = None):
        """Record usage for billing/analytics"""
        try:
            user = User.query.get(user_id)
            billing_period = datetime.utcnow().strftime('%Y-%m')
            
            usage_record = UsageRecord(
                user_id=user_id,
                usage_type=usage_type,
                quantity=quantity,
                cost=cost,
                billing_period=billing_period,
                signalwire_subproject_sid=user.signalwire_subproject_sid if user else None
            )
            
            self.db.session.add(usage_record)
            
            # Update AI response count if applicable
            if usage_type == 'ai_responses' and user:
                user.increment_ai_response_count()
            
        except Exception as e:
            self.logger.error(f"Record usage error: {e}")
    
    def _queue_ai_response(self, user: User, client: Client, incoming_message: Message):
        """Queue AI response generation"""
        try:
            if not user.can_make_ai_response():
                self.logger.warning(f"AI response limit exceeded for user {user.id}")
                return
            
            # Generate AI response (implement AI service integration)
            ai_response = self._generate_ai_response(user, incoming_message.body)
            
            if ai_response:
                # Send AI response
                self.send_message(
                    user_id=user.id,
                    to_number=client.phone_number,
                    body=ai_response,
                    client_id=client.id,
                    ai_generated=True
                )
                
                # Record AI usage
                self._record_usage(user.id, 'ai_responses', 1)
                
        except Exception as e:
            self.logger.error(f"AI response error: {e}")
    
    def _generate_ai_response(self, user: User, message_body: str) -> Optional[str]:
        """Generate AI response - placeholder for AI integration"""
        # TODO: Implement actual AI service integration with LLM_SERVER_URL
        return f"Thanks for your message! I'll get back to you soon."


# =============================================================================
# CLIENT SERVICE
# =============================================================================

class ClientService(BaseService):
    """Handles client/contact management"""
    
    def create_client(self, user_id: int, phone_number: str, name: str = None, 
                     email: str = None, notes: str = None, tags: str = None) -> Tuple[Dict, int]:
        """Create a new client"""
        try:
            # Check if client already exists
            existing_client = Client.query.filter_by(
                user_id=user_id, 
                phone_number=phone_number
            ).first()
            
            if existing_client:
                return self._create_response(False, error="Client already exists", code=409)
            
            client = Client(
                user_id=user_id,
                phone_number=phone_number,
                name=name,
                email=email,
                notes=notes,
                tags=tags
            )
            
            self.db.session.add(client)
            self.db.session.commit()
            
            # Log activity
            self._log_activity(user_id, 'client_created', 'client', str(client.id))
            
            return self._create_response(
                True, 
                data=client.to_dict(), 
                message="Client created successfully",
                code=201
            )
            
        except Exception as e:
            self.db.session.rollback()
            self.logger.error(f"Create client error: {e}")
            return self._create_response(False, error="Failed to create client", code=500)
    
    def get_user_clients(self, user_id: int, limit: int = 50, offset: int = 0) -> Tuple[Dict, int]:
        """Get user's clients"""
        try:
            clients = Client.query.filter_by(user_id=user_id).limit(limit).offset(offset).all()
            
            return self._create_response(
                True, 
                data=[client.to_dict() for client in clients]
            )
            
        except Exception as e:
            self.logger.error(f"Get clients error: {e}")
            return self._create_response(False, error="Failed to get clients", code=500)


# =============================================================================
# SERVICE MANAGER (SINGLETON)
# =============================================================================

class ServiceManager:
    """Unified service manager - single point of access"""
    
    _instance = None
    _services = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._services:
            self._services = {
                'user': UserService(),
                'messaging': MessagingService(),
                'billing': BillingService(),
                'client': ClientService(),
                'signalwire': SignalWireService()
            }
    
    def get_user_service(self) -> UserService:
        return self._services['user']
    
    def get_messaging_service(self) -> MessagingService:
        return self._services['messaging']
    
    def get_billing_service(self) -> BillingService:
        return self._services['billing']
    
    def get_client_service(self) -> ClientService:
        return self._services['client']
    
    def get_signalwire_service(self) -> SignalWireService:
        return self._services['signalwire']


# =============================================================================
# SERVICE FACTORY FUNCTIONS
# =============================================================================

def get_service_manager() -> ServiceManager:
    """Get the service manager instance"""
    return ServiceManager()

def get_user_service() -> UserService:
    """Get user service instance"""
    return get_service_manager().get_user_service()

def get_messaging_service() -> MessagingService:
    """Get messaging service instance"""
    return get_service_manager().get_messaging_service()

def get_billing_service() -> BillingService:
    """Get billing service instance"""
    return get_service_manager().get_billing_service()

def get_client_service() -> ClientService:
    """Get client service instance"""
    return get_service_manager().get_client_service()

def get_signalwire_service() -> SignalWireService:
    """Get SignalWire service instance"""
    return get_service_manager().get_signalwire_service()