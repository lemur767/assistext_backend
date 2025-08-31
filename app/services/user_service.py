import os
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from flask import current_app
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import User, Subscription, SubscriptionPlan, Client

from app.services.billing_service import BillingService
from app.utils.validators import validate_email, validate_phone_number


class UserService:
    """Complete user management with trial handling and SignalWire integration"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.signalwire_service = SignalWireService()
        self.billing_service = BillingService()
        self.notification_service = NotificationService()
    
    def register_user(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Complete user registration with validation and setup
        """
        try:
            # Validate input data
            validation_result = self._validate_registration_data(user_data)
            if not validation_result['valid']:
                return {'success': False, 'errors': validation_result['errors']}
            
            # Check for existing user
            existing_user = User.query.filter(
                (User.email == user_data['email']) | 
                (User.username == user_data['username'])
            ).first()
            
            if existing_user:
                return {
                    'success': False, 
                    'error': 'User with this email or username already exists'
                }
            
            # Create user
            user = User(
                username=user_data['username'],
                email=user_data['email'],
                password=user_data['password'],
                first_name=user_data.get('first_name'),
                last_name=user_data.get('last_name'),
                phone_number=user_data.get('phone_number'),
                timezone=user_data.get('timezone', 'UTC')
            )
            
            db.session.add(user)
            db.session.flush()  # Get user ID
            
            # Create SignalWire subproject
            subproject_result = self.signalwire_service.create_subproject(
                user_id=user.id,
                name=f"AssisText-{user.username}"
            )
            
            if subproject_result['success']:
                user.signalwire_subproject_id = subproject_result['subproject_id']
            else:
                self.logger.warning(f"Failed to create SignalWire subproject for user {user.id}")
            
            db.session.commit()
            
            # Send welcome email
            self.notification_service.send_welcome_email(user)
            
            # Generate JWT tokens
            tokens = user.generate_tokens()
            
            return {
                'success': True,
                'user': user.to_dict(),
                'tokens': tokens,
                'message': 'User registered successfully'
            }
            
        except IntegrityError as e:
            db.session.rollback()
            self.logger.error(f"Database integrity error during registration: {str(e)}")
            return {'success': False, 'error': 'Registration failed due to duplicate data'}
        
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Registration error: {str(e)}")
            return {'success': False, 'error': 'Registration failed'}
    
    def authenticate_user(self, email_or_username: str, password: str) -> Dict[str, Any]:
        """
        Authenticate user and return tokens
        """
        try:
            # Find user by email or username
            user = User.query.filter(
                (User.email == email_or_username) | 
                (User.username == email_or_username)
            ).first()
            
            if not user or not user.check_password(password):
                return {'success': False, 'error': 'Invalid credentials'}
            
            if not user.is_active:
                return {'success': False, 'error': 'Account is deactivated'}
            
            # Update last login
            user.last_login = datetime.utcnow()
            user.last_activity = datetime.utcnow()
            
            # Check trial status
            if user.is_trial_expired():
                user.trial_status = 'expired'
            
            db.session.commit()
            
            # Generate tokens
            tokens = user.generate_tokens()
            
            return {
                'success': True,
                'user': user.to_dict(),
                'tokens': tokens
            }
            
        except Exception as e:
            self.logger.error(f"Authentication error: {str(e)}")
            return {'success': False, 'error': 'Authentication failed'}
    
    def start_trial(self, user_id: int, payment_method_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Start trial with payment method validation
        """
        try:
            user = User.query.get(user_id)
            if not user:
                return {'success': False, 'error': 'User not found'}
            
            if not user.is_trial_eligible:
                return {'success': False, 'error': 'User not eligible for trial'}
            
            # Validate payment method with Stripe
            payment_result = self.billing_service.add_payment_method(
                user_id=user_id,
                payment_method_data=payment_method_data
            )
            
            if not payment_result['success']:
                return {'success': False, 'error': 'Invalid payment method'}
            
            # Start trial
            user.start_trial()
            
            # Get default trial plan
            trial_plan = SubscriptionPlan.query.filter_by(name='Professional').first()
            if not trial_plan:
                return {'success': False, 'error': 'No trial plan available'}
            
            # Create trial subscription
            subscription_result = self.billing_service.create_trial_subscription(
                user_id=user_id,
                plan_id=trial_plan.id
            )
            
            if subscription_result['success']:
                # Purchase phone number
                phone_result = self.signalwire_service.purchase_phone_number(
                    user_id=user_id,
                    area_code=payment_method_data.get('preferred_area_code', '416')
                )
                
                if phone_result['success']:
                    user.signalwire_phone_number = phone_result['phone_number']
                    user.signalwire_phone_number_sid = phone_result['phone_number_sid']
                    db.session.commit()
                
                return {
                    'success': True,
                    'trial_ends_at': user.trial_ends_at.isoformat(),
                    'phone_number': user.signalwire_phone_number,
                    'message': 'Trial started successfully'
                }
            
            return {'success': False, 'error': 'Failed to create trial subscription'}
            
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Trial start error: {str(e)}")
            return {'success': False, 'error': 'Failed to start trial'}
    
    def get_user_profile(self, user_id: int) -> Dict[str, Any]:
        """
        Get complete user profile with subscription and usage info
        """
        try:
            user = User.query.get(user_id)
            if not user:
                return {'success': False, 'error': 'User not found'}
            
            profile_data = user.to_dict()
            
            # Add subscription info
            if user.subscription:
                profile_data['subscription'] = user.subscription.to_dict()
            
            # Add usage stats
            usage_stats = self._get_user_usage_stats(user_id)
            profile_data['usage_stats'] = usage_stats
            
            # Add client count
            profile_data['client_count'] = user.clients.count()
            
            return {
                'success': True,
                'profile': profile_data
            }
            
        except Exception as e:
            self.logger.error(f"Profile fetch error: {str(e)}")
            return {'success': False, 'error': 'Failed to fetch profile'}
    
    def update_user_profile(self, user_id: int, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update user profile information
        """
        try:
            user = User.query.get(user_id)
            if not user:
                return {'success': False, 'error': 'User not found'}
            
            # Validate update data
            validation_result = self._validate_profile_update(update_data)
            if not validation_result['valid']:
                return {'success': False, 'errors': validation_result['errors']}
            
            # Update allowed fields
            allowed_fields = [
                'first_name', 'last_name', 'phone_number', 
                'timezone', 'email'  # Email requires verification
            ]
            
            for field in allowed_fields:
                if field in update_data:
                    setattr(user, field, update_data[field])
            
            user.updated_at = datetime.utcnow()
            db.session.commit()
            
            return {
                'success': True,
                'user': user.to_dict(),
                'message': 'Profile updated successfully'
            }
            
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Profile update error: {str(e)}")
            return {'success': False, 'error': 'Failed to update profile'}
    
    def check_trial_warnings(self) -> None:
        """
        Check and send trial warning notifications
        """
        try:
            # Find users with active trials ending in 3 days
            warning_date = datetime.utcnow() + timedelta(days=3)
            
            users_to_warn = User.query.filter(
                User.trial_status == 'active',
                User.trial_ends_at <= warning_date,
                User.trial_warning_sent == False
            ).all()
            
            for user in users_to_warn:
                self.notification_service.send_trial_warning_email(user)
                user.trial_warning_sent = True
            
            # Find expired trials
            expired_users = User.query.filter(
                User.trial_status == 'active',
                User.trial_ends_at <= datetime.utcnow()
            ).all()
            
            for user in expired_users:
                user.trial_status = 'expired'
                self.notification_service.send_trial_expired_email(user)
            
            db.session.commit()
            
        except Exception as e:
            self.logger.error(f"Trial warning check error: {str(e)}")
            db.session.rollback()
    
    def _validate_registration_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate registration data"""
        errors = []
        
        # Required fields
        required_fields = ['username', 'email', 'password']
        for field in required_fields:
            if not data.get(field):
                errors.append(f'{field} is required')
        
        # Email validation
        if data.get('email') and not validate_email(data['email']):
            errors.append('Invalid email format')
        
        # Phone validation
        if data.get('phone_number') and not validate_phone_number(data['phone_number']):
            errors.append('Invalid phone number format')
        
        # Password strength
        password = data.get('password', '')
        if len(password) < 8:
            errors.append('Password must be at least 8 characters')
        
        return {
            'valid': len(errors) == 0,
            'errors': errors
        }
    
    def _validate_profile_update(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate profile update data"""
        errors = []
        
        # Email validation
        if data.get('email') and not validate_email(data['email']):
            errors.append('Invalid email format')
        
        # Phone validation
        if data.get('phone_number') and not validate_phone_number(data['phone_number']):
            errors.append('Invalid phone number format')
        
        return {
            'valid': len(errors) == 0,
            'errors': errors
        }
    
    def _get_user_usage_stats(self, user_id: int) -> Dict[str, Any]:
        """Get user usage statistics"""
        from app.models import UsageRecord
        
        # Get current month usage
        start_of_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        usage_records = UsageRecord.query.filter(
            UsageRecord.user_id == user_id,
            UsageRecord.created_at >= start_of_month
        ).all()
        
        stats = {
            'sms_sent': 0,
            'sms_received': 0,
            'ai_responses': 0,
            'total_cost': 0.0
        }
        
        for record in usage_records:
            if record.metric_type == 'sms_sent':
                stats['sms_sent'] += record.quantity
            elif record.metric_type == 'sms_received':
                stats['sms_received'] += record.quantity
            elif record.metric_type == 'ai_response':
                stats['ai_responses'] += record.quantity
            
            if record.total_cost:
                stats['total_cost'] += float(record.total_cost)
        
        return stats