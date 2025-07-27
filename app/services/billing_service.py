from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from app.extensions import db
from app.models.billing import Subscription, SubscriptionPlan, Invoice, Payment, UsageRecord
from app.models.user import User
from app.utils.external_clients import StripeClient


class BillingService:
    """Unified billing operations service"""
    
    # =============================================================================
    # SUBSCRIPTION MANAGEMENT
    # =============================================================================
    
    @staticmethod
    def create_subscription(user_id: int, plan_id: int, payment_method_id: str) -> Subscription:
        """Create new subscription with payment setup"""
        try:
            user = User.query.get_or_404(user_id)
            plan = SubscriptionPlan.query.get_or_404(plan_id)
            
            # Create Stripe subscription
            stripe_client = StripeClient()
            stripe_sub = stripe_client.create_subscription(
                customer_id=user.stripe_customer_id,
                price_id=plan.stripe_price_id,
                payment_method_id=payment_method_id
            )
            
            # Create local subscription record
            subscription = Subscription(
                user_id=user_id,
                plan_id=plan_id,
                status=stripe_sub.status,
                billing_cycle='monthly',  # Default
                current_period_start=datetime.fromtimestamp(stripe_sub.current_period_start),
                current_period_end=datetime.fromtimestamp(stripe_sub.current_period_end),
                stripe_subscription_id=stripe_sub.id
            )
            
            db.session.add(subscription)
            db.session.commit()
            
            return subscription
            
        except Exception as e:
            db.session.rollback()
            raise Exception(f"Failed to create subscription: {str(e)}")
    
    @staticmethod
    def cancel_subscription(subscription_id: int, reason: str = None) -> bool:
        """Cancel subscription and cleanup resources"""
        try:
            subscription = Subscription.query.get_or_404(subscription_id)
            
            # Cancel in Stripe
            stripe_client = StripeClient()
            stripe_client.cancel_subscription(subscription.stripe_subscription_id)
            
            # Update local record
            subscription.status = 'canceled'
            subscription.canceled_at = datetime.utcnow()
            subscription.cancellation_reason = reason
            
            db.session.commit()
            return True
            
        except Exception as e:
            db.session.rollback()
            raise Exception(f"Failed to cancel subscription: {str(e)}")
    
    @staticmethod
    def get_user_subscription(user_id: int) -> Optional[Subscription]:
        """Get user's active subscription"""
        return Subscription.query.filter_by(
            user_id=user_id,
            status='active'
        ).first()
    
    # =============================================================================
    # USAGE TRACKING
    # =============================================================================
    
    @staticmethod
    def track_usage(user_id: int, resource_type: str, quantity: int = 1) -> None:
        """Track resource usage for billing"""
        try:
            subscription = BillingService.get_user_subscription(user_id)
            if not subscription:
                return  # No active subscription to track against
            
            # Get current billing period
            period_start = subscription.current_period_start
            period_end = subscription.current_period_end
            
            # Find existing usage record for this period
            usage_record = UsageRecord.query.filter_by(
                user_id=user_id,
                subscription_id=subscription.id,
                resource_type=resource_type,
                period_start=period_start,
                period_end=period_end
            ).first()
            
            if usage_record:
                usage_record.quantity += quantity
            else:
                usage_record = UsageRecord(
                    user_id=user_id,
                    subscription_id=subscription.id,
                    resource_type=resource_type,
                    quantity=quantity,
                    period_start=period_start,
                    period_end=period_end
                )
                db.session.add(usage_record)
            
            db.session.commit()
            
        except Exception as e:
            db.session.rollback()
            raise Exception(f"Failed to track usage: {str(e)}")
    
    @staticmethod
    def get_usage_summary(user_id: int) -> Dict[str, Any]:
        """Get current usage summary for user"""
        subscription = BillingService.get_user_subscription(user_id)
        if not subscription:
            return {}
        
        usage_records = UsageRecord.query.filter_by(
            subscription_id=subscription.id,
            period_start=subscription.current_period_start,
            period_end=subscription.current_period_end
        ).all()
        
        usage_summary = {}
        for record in usage_records:
            usage_summary[record.resource_type] = record.quantity
        
        # Add plan limits
        plan_features = subscription.plan.features or {}
        limits = {
            'sms_messages': plan_features.get('sms_credits_monthly', 0),
            'ai_responses': plan_features.get('ai_responses_monthly', 0)
        }
        
        return {
            'usage': usage_summary,
            'limits': limits,
            'period_start': subscription.current_period_start,
            'period_end': subscription.current_period_end
        }
    
    @staticmethod
    def check_usage_limits(user_id: int, resource_type: str, requested_quantity: int = 1) -> bool:
        """Check if user can use more of a resource"""
        usage_summary = BillingService.get_usage_summary(user_id)
        if not usage_summary:
            return True  # No subscription = unlimited (trial mode)
        
        current_usage = usage_summary['usage'].get(resource_type, 0)
        limit = usage_summary['limits'].get(resource_type, 0)
        
        return (current_usage + requested_quantity) <= limit
    
    # =============================================================================
    # INVOICE MANAGEMENT
    # =============================================================================
    
    @staticmethod
    def generate_invoice(subscription_id: int) -> Invoice:
        """Generate invoice for subscription"""
        try:
            subscription = Subscription.query.get_or_404(subscription_id)
            plan = subscription.plan
            
            # Create invoice
            invoice = Invoice(
                user_id=subscription.user_id,
                subscription_id=subscription_id,
                invoice_number=BillingService._generate_invoice_number(),
                status='pending',
                subtotal=plan.monthly_price if subscription.billing_cycle == 'monthly' else plan.annual_price,
                tax_amount=0.0,  # Calculate based on user location
                total_amount=plan.monthly_price if subscription.billing_cycle == 'monthly' else plan.annual_price,
                due_date=datetime.utcnow() + timedelta(days=30)
            )
            
            db.session.add(invoice)
            db.session.commit()
            
            return invoice
            
        except Exception as e:
            db.session.rollback()
            raise Exception(f"Failed to generate invoice: {str(e)}")
    
    @staticmethod
    def process_payment(invoice_id: int, payment_method_id: int) -> Payment:
        """Process payment for invoice"""
        try:
            invoice = Invoice.query.get_or_404(invoice_id)
            
            # Process payment with Stripe
            stripe_client = StripeClient()
            payment_intent = stripe_client.process_payment(
                amount=invoice.total_amount,
                currency='USD',
                payment_method_id=payment_method_id
            )
            
            # Create payment record
            payment = Payment(
                user_id=invoice.user_id,
                invoice_id=invoice_id,
                payment_method_id=payment_method_id,
                amount=invoice.total_amount,
                currency='USD',
                status=payment_intent.status,
                stripe_payment_intent_id=payment_intent.id,
                processed_at=datetime.utcnow()
            )
            
            db.session.add(payment)
            
            # Update invoice status
            if payment_intent.status == 'succeeded':
                invoice.status = 'paid'
                invoice.paid_at = datetime.utcnow()
            
            db.session.commit()
            
            return payment
            
        except Exception as e:
            db.session.rollback()
            raise Exception(f"Failed to process payment: {str(e)}")
    
    @staticmethod
    def _generate_invoice_number() -> str:
        """Generate unique invoice number"""
        timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
        return f"INV-{timestamp}"