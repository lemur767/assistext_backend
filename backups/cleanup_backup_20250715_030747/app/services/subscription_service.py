from app.models.billing import Subscription
from app.models.signalwire_account import SignalWireAccount, SignalWirePhoneNumber
from app.models.user import User
from app.extensions import db
from datetime import datetime, timedelta
import logging
from typing import Dict, Optional
from flask import current_app

import secrets
from app.utils.signalwire import get_signalwire_client

class SubscriptionService:
    """Service for managing subscriptions with SignalWire integration"""
    
    @staticmethod
    def create_subscription_with_signalwire(user_id: int, plan_id: int, 
                                          stripe_subscription_id: str = None) -> Dict:
        """
        Create subscription and automatically provision SignalWire resources
        """
        try:
            # Get user and validate
            user = User.query.get(user_id)
            if not user:
                raise ValueError(f"User {user_id} not found")
            
            # Create subscription record
            subscription = Subscription(
                user_id=user_id,
                plan_id=plan_id,
                stripe_subscription_id=stripe_subscription_id,
                status='active',
                start_date=datetime.utcnow(),
                current_period_start=datetime.utcnow(),
                current_period_end=datetime.utcnow() + timedelta(days=30)
            )
            
            db.session.add(subscription)
            db.session.flush()  # Get subscription ID
            
            # Create SignalWire subaccount
            signalwire_account = SubscriptionService._create_signalwire_subaccount(
                user, subscription
            )
            
            if not signalwire_account:
                db.session.rollback()
                raise Exception("Failed to create SignalWire subaccount")
            
            # Provision Canadian phone number
            phone_number = SubscriptionService._provision_canadian_number(
                signalwire_account, user.username
            )
            
            if not phone_number:
                db.session.rollback()
                raise Exception("Failed to provision Canadian phone number")
            
            db.session.commit()
            
            return {
                'success': True,
                'subscription': subscription.to_dict(),
                'signalwire_account': signalwire_account.to_dict(),
                'phone_number': phone_number.to_dict()
            }
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Subscription creation failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def _create_signalwire_subaccount(user: User, subscription: Subscription) -> Optional[SignalWireAccount]:
        """Create SignalWire subaccount for user"""
        
        # Get main SignalWire client
        client = get_signalwire_client()
        
        # Create subaccount
        friendly_name = f"SMS AI - {user.username} ({user.email})"
        subaccount_data = client.create_subaccount(friendly_name)
        
        if not subaccount_data:
            return None
        
        subaccount_sid = subaccount_data['sid']
        
        # Create API token for subaccount
        token_name = f"API Token - {user.username}"
        token_data = client.create_api_token(subaccount_sid, token_name)
        
        if not token_data:
            return None
        
        # Get plan limits
        plan_limits = SubscriptionService._get_plan_limits(subscription.plan_id)
        
        # Create SignalWire account record
        signalwire_account = SignalWireAccount(
            user_id=user.id,
            subscription_id=subscription.id,
            subaccount_sid=subaccount_sid,
            api_token=token_data['secret'],  # Store securely in production
            project_id=subaccount_sid,
            space_url=current_app.config['SIGNALWIRE_SPACE_URL'],
            monthly_limit=plan_limits['monthly_messages']
        )
        
        db.session.add(signalwire_account)
        return signalwire_account
    
    @staticmethod
    def _provision_canadian_number(signalwire_account: SignalWireAccount, 
                                 username: str) -> Optional[SignalWirePhoneNumber]:
        """Provision a Canadian phone number for the account"""
        
        # Get SignalWire client for main account
        client = get_signalwire_client()
        
        # Search for available Canadian numbers
        # Prefer major Canadian cities: Toronto (416/647), Vancouver (604/778), 
        # Montreal (514/438), Calgary (403/587)
        preferred_area_codes = ['416', '604', '514', '403', '647', '778', '438', '587']
        
        available_number = None
        for area_code in preferred_area_codes:
            numbers = client.search_canadian_numbers(area_code=area_code, limit=5)
            if numbers:
                available_number = numbers[0]
                break
        
        # If no preferred area code available, get any Canadian number
        if not available_number:
            numbers = client.search_canadian_numbers(limit=10)
            if numbers:
                available_number = numbers[0]
        
        if not available_number:
            current_app.logger.error("No Canadian numbers available")
            return None
        
        # Purchase the number for the subaccount
        phone_number = available_number['phone_number']
        friendly_name = f"SMS AI - {username}"
        
        purchase_result = client.purchase_phone_number(
            phone_number=phone_number,
            subaccount_sid=signalwire_account.subaccount_sid,
            friendly_name=friendly_name
        )
        
        if not purchase_result:
            return None
        
        # Create phone number record
        phone_number_record = SignalWirePhoneNumber(
            account_id=signalwire_account.id,
            phone_number=phone_number,
            friendly_name=friendly_name,
            country_code='CA',
            monthly_cost=1.00  # Approximate CAD cost
        )
        
        phone_number_record.set_capabilities({
            'sms': True,
            'voice': True,
            'mms': available_number.get('mms', False)
        })
        
        db.session.add(phone_number_record)
        return phone_number_record
    
    @staticmethod
    def _get_plan_limits(plan_id: int) -> Dict:
        """Get plan limits based on subscription plan"""
        plan_limits = {
            1: {'monthly_messages': 500, 'max_profiles': 1},     # Free
            2: {'monthly_messages': 2000, 'max_profiles': 3},    # Basic  
            3: {'monthly_messages': 10000, 'max_profiles': 10},  # Professional
            4: {'monthly_messages': 50000, 'max_profiles': 50}   # Enterprise
        }
        
        return plan_limits.get(plan_id, plan_limits[1])
    
    @staticmethod
    def cancel_subscription(subscription_id: int) -> Dict:
        """Cancel subscription and cleanup SignalWire resources"""
        try:
            subscription = Subscription.query.get(subscription_id)
            if not subscription:
                raise ValueError("Subscription not found")
            
            # Get SignalWire account
            signalwire_account = subscription.signalwire_account
            if signalwire_account:
                # Deactivate account
                signalwire_account.is_active = False
                
                # Deactivate phone numbers
                for phone_number in signalwire_account.phone_numbers:
                    phone_number.is_active = False
                    phone_number.is_assigned = False
            
            # Update subscription status
            subscription.status = 'cancelled'
            subscription.cancelled_at = datetime.utcnow()
            
            db.session.commit()
            
            return {'success': True, 'message': 'Subscription cancelled successfully'}
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Subscription cancellation failed: {e}")
            return {'success': False, 'error': str(e)}
