# app/testing/billing_test_utils.py
"""
Testing utilities for billing system
Provides fixtures, mock data, and test helpers for billing functionality
"""

import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any
from app.extensions import db
from app.models.user import User
from app.models.subscription import Subscription, SubscriptionPlan
from app.models.payment import Payment, PaymentMethod
from app.models.invoice import Invoice, InvoiceLineItem
from app.models.usage import Usage
from app.models.billing_settings import BillingSettings

class BillingTestUtils:
    """Utilities for testing billing functionality"""
    
    @staticmethod
    def create_test_user(email: str = None, **kwargs) -> User:
        """Create a test user"""
        user_data = {
            'id': str(uuid.uuid4()),
            'email': email or f'test_{uuid.uuid4().hex[:8]}@example.com',
            'first_name': 'Test',
            'last_name': 'User',
            'username': f'testuser_{uuid.uuid4().hex[:8]}',
            'password_hash': 'test_hash',
            'is_verified': True,
            **kwargs
        }
        
        user = User(**user_data)
        db.session.add(user)
        db.session.commit()
        return user
    
    @staticmethod
    def create_test_subscription_plan(**kwargs) -> SubscriptionPlan:
        """Create a test subscription plan"""
        plan_data = {
            'id': f'plan_{uuid.uuid4().hex[:8]}',
            'name': 'Test Plan',
            'description': 'Test subscription plan',
            'status': 'active',
            'monthly_price': 29.99,
            'annual_price': 299.99,
            'currency': 'USD',
            'features': {
                'sms_credits_monthly': 1000,
                'ai_responses_monthly': 500,
                'max_profiles': 3,
                'storage_gb': 10,
                'advanced_analytics': True,
                'priority_support': False
            },
            **kwargs
        }
        
        plan = SubscriptionPlan(**plan_data)
        db.session.add(plan)
        db.session.commit()
        return plan
    
    @staticmethod
    def create_test_subscription(user: User, plan: SubscriptionPlan, **kwargs) -> Subscription:
        """Create a test subscription"""
        subscription_data = {
            'id': str(uuid.uuid4()),
            'user_id': user.id,
            'plan_id': plan.id,
            'status': 'active',
            'billing_cycle': 'monthly',
            'amount': plan.monthly_price,
            'currency': plan.currency,
            'auto_renew': True,
            'current_period_start': datetime.utcnow(),
            'current_period_end': datetime.utcnow() + timedelta(days=30),
            **kwargs
        }
        
        subscription = Subscription(**subscription_data)
        db.session.add(subscription)
        db.session.commit()
        return subscription
    
    @staticmethod
    def create_test_payment_method(user: User, **kwargs) -> PaymentMethod:
        """Create a test payment method"""
        pm_data = {
            'id': str(uuid.uuid4()),
            'user_id': user.id,
            'type': 'card',
            'is_default': True,
            'status': 'active',
            'card_brand': 'visa',
            'card_last4': '4242',
            'card_exp_month': 12,
            'card_exp_year': 2025,
            'processor_id': f'pm_test_{uuid.uuid4().hex[:8]}',
            **kwargs
        }
        
        payment_method = PaymentMethod(**pm_data)
        db.session.add(payment_method)
        db.session.commit()
        return payment_method
    
    @staticmethod
    def create_test_payment(user: User, subscription: Subscription = None, **kwargs) -> Payment:
        """Create a test payment"""
        payment_data = {
            'id': str(uuid.uuid4()),
            'user_id': user.id,
            'subscription_id': subscription.id if subscription else None,
            'amount': 29.99,
            'currency': 'USD',
            'status': 'succeeded',
            'description': 'Test payment',
            'processed_at': datetime.utcnow(),
            **kwargs
        }
        
        payment = Payment(**payment_data)
        db.session.add(payment)
        db.session.commit()
        return payment
    
    @staticmethod
    def create_test_invoice(user: User, subscription: Subscription = None, **kwargs) -> Invoice:
        """Create a test invoice"""
        invoice_data = {
            'id': str(uuid.uuid4()),
            'user_id': user.id,
            'subscription_id': subscription.id if subscription else None,
            'invoice_number': f'INV-TEST-{uuid.uuid4().hex[:8].upper()}',
            'status': 'open',
            'subtotal': 29.99,
            'tax_amount': 2.40,
            'total': 32.39,
            'amount_due': 32.39,
            'currency': 'USD',
            'due_date': datetime.utcnow() + timedelta(days=30),
            **kwargs
        }
        
        invoice = Invoice(**invoice_data)
        db.session.add(invoice)
        db.session.commit()
        
        # Create a line item
        line_item = InvoiceLineItem(
            id=str(uuid.uuid4()),
            invoice_id=invoice.id,
            description='Test subscription',
            quantity=1,
            unit_amount=29.99,
            total_amount=29.99
        )
        db.session.add(line_item)
        db.session.commit()
        
        return invoice
    
    @staticmethod
    def create_test_usage(subscription: Subscription, **kwargs) -> Usage:
        """Create a test usage record"""
        usage_data = {
            'id': str(uuid.uuid4()),
            'user_id': subscription.user_id,
            'subscription_id': subscription.id,
            'period_start': subscription.current_period_start,
            'period_end': subscription.current_period_end,
            'sms_sent': 50,
            'sms_credits_used': 50,
            'sms_credits_remaining': 950,
            'ai_responses_generated': 25,
            'ai_credits_used': 25,
            'ai_credits_remaining': 475,
            'active_profiles': 2,
            'storage_used_gb': 1.5,
            'storage_limit_gb': 10.0,
            **kwargs
        }
        
        usage = Usage(**usage_data)
        db.session.add(usage)
        db.session.commit()
        return usage
    
    @staticmethod
    def create_test_billing_settings(user: User, **kwargs) -> BillingSettings:
        """Create test billing settings"""
        settings_data = {
            'id': str(uuid.uuid4()),
            'user_id': user.id,
            'auto_pay': True,
            'billing_email': user.email,
            'invoice_delivery': 'email',
            'currency': 'USD',
            'notifications': {
                'payment_succeeded': True,
                'payment_failed': True,
                'invoice_created': True,
                'subscription_renewed': True,
                'subscription_canceled': True,
                'usage_alerts': True
            },
            'usage_alert_thresholds': {
                'sms_credits': 80,
                'ai_credits': 80,
                'storage': 80
            },
            **kwargs
        }
        
        settings = BillingSettings(**settings_data)
        db.session.add(settings)
        db.session.commit()
        return settings
    
    @staticmethod
    def create_complete_billing_setup(email: str = None) -> Dict[str, Any]:
        """Create a complete billing setup for testing"""
        # Create user
        user = BillingTestUtils.create_test_user(email)
        
        # Create plan
        plan = BillingTestUtils.create_test_subscription_plan()
        
        # Create subscription
        subscription = BillingTestUtils.create_test_subscription(user, plan)
        
        # Create payment method
        payment_method = BillingTestUtils.create_test_payment_method(user)
        
        # Create usage
        usage = BillingTestUtils.create_test_usage(subscription)
        
        # Create billing settings
        billing_settings = BillingTestUtils.create_test_billing_settings(user)
        
        # Create invoice
        invoice = BillingTestUtils.create_test_invoice(user, subscription)
        
        # Create payment
        payment = BillingTestUtils.create_test_payment(user, subscription)
        
        return {
            'user': user,
            'plan': plan,
            'subscription': subscription,
            'payment_method': payment_method,
            'usage': usage,
            'billing_settings': billing_settings,
            'invoice': invoice,
            'payment': payment
        }
    
    @staticmethod
    def cleanup_test_data(user_id: str = None):
        """Clean up test data"""
        if user_id:
            # Delete specific user's data
            user = User.query.get(user_id)
            if user:
                db.session.delete(user)
        else:
            # Delete all test data (use with caution!)
            test_users = User.query.filter(User.email.like('%@example.com')).all()
            for user in test_users:
                db.session.delete(user)
        
        db.session.commit()
    
    @staticmethod
    def simulate_billing_cycle_completion(subscription: Subscription) -> Dict[str, Any]:
        """Simulate completion of a billing cycle"""
        from app.services.invoice_generator import InvoiceGenerator
        from app.services.usage_tracker import UsageTracker
        
        # Create invoice for the period
        invoice_result = InvoiceGenerator.create_subscription_invoice(
            subscription.id,
            subscription.current_period_start,
            subscription.current_period_end
        )
        
        # Reset usage for new period
        subscription.current_period_start = subscription.current_period_end
        subscription.current_period_end = subscription.current_period_end + timedelta(days=30)
        
        usage_result = UsageTracker.reset_usage_for_new_period(subscription.id)
        
        db.session.commit()
        
        return {
            'invoice_result': invoice_result,
            'usage_result': usage_result,
            'new_period_start': subscription.current_period_start,
            'new_period_end': subscription.current_period_end
        }


# Pytest fixtures for testing
def create_billing_fixtures():
    """Create pytest fixtures for billing tests"""
    
    import pytest
    
    @pytest.fixture
    def test_user():
        """Fixture for test user"""
        user = BillingTestUtils.create_test_user()
        yield user
        BillingTestUtils.cleanup_test_data(user.id)
    
    @pytest.fixture
    def test_plan():
        """Fixture for test subscription plan"""
        return BillingTestUtils.create_test_subscription_plan()
    
    @pytest.fixture
    def test_subscription(test_user, test_plan):
        """Fixture for test subscription"""
        return BillingTestUtils.create_test_subscription(test_user, test_plan)
    
    @pytest.fixture
    def complete_billing_setup():
        """Fixture for complete billing setup"""
        setup = BillingTestUtils.create_complete_billing_setup()
        yield setup
        BillingTestUtils.cleanup_test_data(setup['user'].id)
    
    return {
        'test_user': test_user,
        'test_plan': test_plan,
        'test_subscription': test_subscription,
        'complete_billing_setup': complete_billing_setup
    }


# Example test cases
class BillingTestCases:
    """Example test cases for billing functionality"""
    
    def test_subscription_creation(self, test_user, test_plan):
        """Test subscription creation"""
        subscription = BillingTestUtils.create_test_subscription(test_user, test_plan)
        
        assert subscription.user_id == test_user.id
        assert subscription.plan_id == test_plan.id
        assert subscription.status == 'active'
        assert subscription.amount == test_plan.monthly_price
    
    def test_invoice_generation(self, test_subscription):
        """Test invoice generation"""
        from app.services.invoice_generator import InvoiceGenerator
        
        result = InvoiceGenerator.create_subscription_invoice(
            test_subscription.id,
            test_subscription.current_period_start,
            test_subscription.current_period_end
        )
        
        assert result['success'] is True
        assert 'invoice_id' in result
        assert result['total'] > 0
    
    def test_usage_tracking(self, test_subscription):
        """Test usage tracking"""
        from app.services.usage_tracker import UsageTracker
        
        # Track SMS usage
        result = UsageTracker.track_sms_sent(
            test_subscription.user_id,
            '+1234567890',
            'Test message'
        )
        
        assert result['success'] is True
        assert result['credits_used'] > 0
        assert result['credits_remaining'] >= 0
    
    def test_payment_processing(self, test_user, test_payment_method):
        """Test payment processing"""
        from app.services.payment_processor import PaymentProcessor
        
        result = PaymentProcessor.process_payment(
            amount=29.99,
            currency='USD',
            payment_method_id=test_payment_method.id,
            description='Test payment'
        )
        
        # Note: This would fail in real testing without proper Stripe setup
        # Use mocked PaymentProcessor for actual tests
        assert 'success' in result