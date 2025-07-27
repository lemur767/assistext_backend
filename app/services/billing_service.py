
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from decimal import Decimal
import logging

from flask import current_app
from sqlalchemy import and_, or_, func
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.models.billing import (
    Subscription, SubscriptionPlan, Invoice, InvoiceItem,
    PaymentMethod, Payment, UsageRecord
)
from app.models.user import User
from app.utils.stripe_client import StripeClient


class BillingService:
    """Unified billing operations service"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.stripe_client = StripeClient()
    
    # =============================================================================
    # SUBSCRIPTION MANAGEMENT
    # =============================================================================
    
    def create_subscription(self, user_id: int, plan_id: int, 
                          payment_method_id: str = None, billing_cycle: str = 'monthly') -> Subscription:
        """Create new subscription with payment setup"""
        try:
            user = User.query.get_or_404(user_id)
            plan = SubscriptionPlan.query.get_or_404(plan_id)
            
            # Check if user already has active subscription
            existing_sub = self.get_user_active_subscription(user_id)
            if existing_sub:
                raise ValueError("User already has an active subscription")
            
            # Calculate pricing
            amount = plan.monthly_price if billing_cycle == 'monthly' else plan.annual_price
            period_start = datetime.utcnow()
            period_end = self._calculate_period_end(period_start, billing_cycle)
            
            # Create Stripe subscription if payment method provided
            stripe_subscription_id = None
            if payment_method_id:
                stripe_sub = self.stripe_client.create_subscription(
                    customer_id=user.stripe_customer_id,
                    price_id=self._get_stripe_price_id(plan, billing_cycle),
                    payment_method_id=payment_method_id
                )
                stripe_subscription_id = stripe_sub.id
            
            # Create local subscription record
            subscription = Subscription(
                user_id=user_id,
                plan_id=plan_id,
                status='trialing' if plan.trial_period_days > 0 else 'active',
                billing_cycle=billing_cycle,
                current_period_start=period_start,
                current_period_end=period_end,
                amount=amount,
                currency=plan.currency,
                stripe_subscription_id=stripe_subscription_id
            )
            
            # Set trial end if applicable
            if plan.trial_period_days > 0:
                subscription.trial_start = period_start
                subscription.trial_end = period_start + timedelta(days=plan.trial_period_days)
            
            db.session.add(subscription)
            db.session.commit()
            
            self.logger.info(f"Created subscription {subscription.id} for user {user_id}")
            return subscription
            
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Failed to create subscription: {str(e)}")
            raise Exception(f"Failed to create subscription: {str(e)}")
    
    def update_subscription(self, subscription_id: int, **updates) -> Subscription:
        """Update subscription settings"""
        try:
            subscription = Subscription.query.get_or_404(subscription_id)
            
            # Handle plan changes
            if 'plan_id' in updates:
                new_plan = SubscriptionPlan.query.get_or_404(updates['plan_id'])
                old_amount = subscription.amount
                new_amount = (new_plan.monthly_price if subscription.billing_cycle == 'monthly' 
                            else new_plan.annual_price)
                
                # Calculate proration if needed
                if new_amount != old_amount:
                    self._handle_plan_change_proration(subscription, new_plan, new_amount)
                
                subscription.plan_id = updates['plan_id']
                subscription.amount = new_amount
            
            # Handle billing cycle changes
            if 'billing_cycle' in updates:
                subscription.billing_cycle = updates['billing_cycle']
                # Recalculate amount based on new cycle
                plan = subscription.plan
                subscription.amount = (plan.monthly_price if updates['billing_cycle'] == 'monthly' 
                                     else plan.annual_price)
            
            # Update other fields
            for field in ['auto_renew', 'metadata']:
                if field in updates:
                    setattr(subscription, field, updates[field])
            
            # Update in Stripe if needed
            if subscription.stripe_subscription_id:
                self.stripe_client.update_subscription(
                    subscription.stripe_subscription_id,
                    updates
                )
            
            db.session.commit()
            self.logger.info(f"Updated subscription {subscription_id}")
            return subscription
            
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Failed to update subscription: {str(e)}")
            raise Exception(f"Failed to update subscription: {str(e)}")
    
    def cancel_subscription(self, subscription_id: int, reason: str = None, 
                          immediate: bool = False) -> bool:
        """Cancel subscription and cleanup resources"""
        try:
            subscription = Subscription.query.get_or_404(subscription_id)
            
            # Cancel in Stripe
            if subscription.stripe_subscription_id:
                self.stripe_client.cancel_subscription(
                    subscription.stripe_subscription_id, 
                    immediately=immediate
                )
            
            # Update local record
            if immediate:
                subscription.status = 'canceled'
                subscription.current_period_end = datetime.utcnow()
            else:
                subscription.status = 'pending_cancel'
                subscription.auto_renew = False
            
            subscription.canceled_at = datetime.utcnow()
            subscription.cancellation_reason = reason
            
            db.session.commit()
            self.logger.info(f"Canceled subscription {subscription_id}")
            return True
            
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Failed to cancel subscription: {str(e)}")
            raise Exception(f"Failed to cancel subscription: {str(e)}")
    
    def get_user_active_subscription(self, user_id: int) -> Optional[Subscription]:
        """Get user's active subscription"""
        return Subscription.query.filter_by(
            user_id=user_id,
            status='active'
        ).first()
    
    def get_subscription_with_plan(self, subscription_id: int) -> Optional[Subscription]:
        """Get subscription with plan details"""
        return Subscription.query.options(
            db.joinedload(Subscription.plan)
        ).get(subscription_id)
    
    # =============================================================================
    # USAGE TRACKING
    # =============================================================================
    
    def track_usage(self, user_id: int, resource_type: str, quantity: int = 1, 
                   metadata: Dict[str, Any] = None) -> None:
        """Track resource usage for billing"""
        try:
            subscription = self.get_user_active_subscription(user_id)
            if not subscription:
                # No active subscription - skip tracking for trial users
                return
            
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
                # Calculate unit cost if applicable
                unit_cost = self._get_unit_cost(subscription.plan, resource_type)
                
                usage_record = UsageRecord(
                    user_id=user_id,
                    subscription_id=subscription.id,
                    resource_type=resource_type,
                    quantity=quantity,
                    unit_cost=unit_cost,
                    total_cost=unit_cost * quantity,
                    period_start=period_start,
                    period_end=period_end,
                    usage_metadata=metadata
                )
                db.session.add(usage_record)
            
            db.session.commit()
            
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Failed to track usage: {str(e)}")
            # Don't raise exception for usage tracking - log and continue
    
    def get_usage_summary(self, user_id: int, period_start: datetime = None, 
                         period_end: datetime = None) -> Dict[str, Any]:
        """Get usage summary for user"""
        subscription = self.get_user_active_subscription(user_id)
        if not subscription:
            return {
                'usage': {},
                'limits': {},
                'period_start': None,
                'period_end': None,
                'percentage_used': {}
            }
        
        # Use subscription period if not specified
        if not period_start:
            period_start = subscription.current_period_start
        if not period_end:
            period_end = subscription.current_period_end
        
        # Get usage records for period
        usage_records = UsageRecord.query.filter_by(
            user_id=user_id,
            subscription_id=subscription.id,
            period_start=period_start,
            period_end=period_end
        ).all()
        
        # Aggregate usage by resource type
        usage_summary = {}
        for record in usage_records:
            usage_summary[record.resource_type] = record.quantity
        
        # Get plan limits
        plan_features = subscription.plan.features or {}
        limits = {
            'sms_messages': plan_features.get('sms_credits_monthly', 0),
            'ai_responses': plan_features.get('ai_responses_monthly', 0),
            'storage_gb': plan_features.get('storage_gb', 0)
        }
        
        # Calculate percentage used
        percentage_used = {}
        for resource_type, limit in limits.items():
            if limit > 0:
                used = usage_summary.get(resource_type, 0)
                percentage_used[resource_type] = min(100, (used / limit) * 100)
        
        return {
            'usage': usage_summary,
            'limits': limits,
            'period_start': period_start,
            'period_end': period_end,
            'percentage_used': percentage_used,
            'subscription_id': subscription.id
        }
    
    def check_usage_limits(self, user_id: int, resource_type: str, 
                          requested_quantity: int = 1) -> Tuple[bool, Dict[str, Any]]:
        """Check if user can use more of a resource"""
        usage_summary = self.get_usage_summary(user_id)
        
        if not usage_summary['limits']:
            # No subscription = unlimited (trial mode)
            return True, {'reason': 'no_subscription', 'unlimited': True}
        
        current_usage = usage_summary['usage'].get(resource_type, 0)
        limit = usage_summary['limits'].get(resource_type, 0)
        
        if limit == 0:
            # Unlimited for this resource
            return True, {'reason': 'unlimited_resource'}
        
        can_use = (current_usage + requested_quantity) <= limit
        
        return can_use, {
            'current_usage': current_usage,
            'limit': limit,
            'requested': requested_quantity,
            'would_total': current_usage + requested_quantity,
            'remaining': max(0, limit - current_usage)
        }
    
    # =============================================================================
    # INVOICE MANAGEMENT
    # =============================================================================
    
    def generate_invoice(self, subscription_id: int, invoice_items: List[Dict] = None) -> Invoice:
        """Generate invoice for subscription"""
        try:
            subscription = Subscription.query.get_or_404(subscription_id)
            plan = subscription.plan
            
            # Generate unique invoice number
            invoice_number = self._generate_invoice_number()
            
            # Calculate invoice amounts
            subtotal = Decimal('0.00')
            
            # Create invoice
            invoice = Invoice(
                user_id=subscription.user_id,
                subscription_id=subscription_id,
                invoice_number=invoice_number,
                status='draft',
                subtotal=subtotal,
                tax_amount=Decimal('0.00'),
                total_amount=subtotal,
                amount_due=subtotal,
                currency=plan.currency,
                invoice_date=datetime.utcnow(),
                due_date=datetime.utcnow() + timedelta(days=30)
            )
            
            db.session.add(invoice)
            db.session.flush()  # Get invoice ID
            
            # Add subscription fee as line item
            subscription_item = InvoiceItem(
                invoice_id=invoice.id,
                description=f"{plan.name} - {subscription.billing_cycle.title()} Plan",
                quantity=1,
                unit_price=subscription.amount,
                total_price=subscription.amount,
                item_type='subscription',
                period_start=subscription.current_period_start,
                period_end=subscription.current_period_end
            )
            db.session.add(subscription_item)
            subtotal += subscription.amount
            
            # Add usage-based items if any
            if invoice_items:
                for item_data in invoice_items:
                    item = InvoiceItem(
                        invoice_id=invoice.id,
                        **item_data
                    )
                    db.session.add(item)
                    subtotal += item.total_price
            
            # Update invoice totals
            invoice.subtotal = subtotal
            invoice.total_amount = subtotal
            invoice.amount_due = subtotal
            
            db.session.commit()
            
            self.logger.info(f"Generated invoice {invoice.invoice_number} for subscription {subscription_id}")
            return invoice
            
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Failed to generate invoice: {str(e)}")
            raise Exception(f"Failed to generate invoice: {str(e)}")
    
    def process_payment(self, invoice_id: int, payment_method_id: int = None) -> Payment:
        """Process payment for invoice"""
        try:
            invoice = Invoice.query.get_or_404(invoice_id)
            
            # Use default payment method if not specified
            if not payment_method_id:
                default_pm = PaymentMethod.query.filter_by(
                    user_id=invoice.user_id,
                    is_default=True
                ).first()
                if default_pm:
                    payment_method_id = default_pm.id
            
            if not payment_method_id:
                raise ValueError("No payment method available")
            
            payment_method = PaymentMethod.query.get_or_404(payment_method_id)
            
            # Process payment with Stripe
            payment_intent = self.stripe_client.process_payment(
                amount=float(invoice.amount_due),
                currency=invoice.currency,
                payment_method_id=payment_method.stripe_payment_method_id
            )
            
            # Create payment record
            payment = Payment(
                user_id=invoice.user_id,
                invoice_id=invoice_id,
                payment_method_id=payment_method_id,
                amount=invoice.amount_due,
                currency=invoice.currency,
                status=payment_intent.status,
                stripe_payment_intent_id=payment_intent.id,
                processed_at=datetime.utcnow()
            )
            
            db.session.add(payment)
            
            # Update invoice status
            if payment_intent.status == 'succeeded':
                invoice.status = 'paid'
                invoice.paid_at = datetime.utcnow()
                invoice.amount_paid = invoice.amount_due
                invoice.amount_due = Decimal('0.00')
            elif payment_intent.status == 'failed':
                invoice.status = 'payment_failed'
                payment.failure_reason = "Payment failed"
            
            db.session.commit()
            
            self.logger.info(f"Processed payment for invoice {invoice.invoice_number}")
            return payment
            
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Failed to process payment: {str(e)}")
            raise Exception(f"Failed to process payment: {str(e)}")
    
    # =============================================================================
    # BILLING ANALYTICS
    # =============================================================================
    
    def get_billing_analytics(self, user_id: int, months_back: int = 12) -> Dict[str, Any]:
        """Get billing analytics for user"""
        start_date = datetime.utcnow() - timedelta(days=months_back * 30)
        
        # Get payment history
        payments = Payment.query.filter(
            Payment.user_id == user_id,
            Payment.created_at >= start_date,
            Payment.status == 'succeeded'
        ).all()
        
        # Calculate metrics
        total_paid = sum(float(p.amount) for p in payments)
        avg_monthly = total_paid / months_back if months_back > 0 else 0
        
        # Get usage trends
        usage_records = UsageRecord.query.filter(
            UsageRecord.user_id == user_id,
            UsageRecord.created_at >= start_date
        ).all()
        
        usage_by_month = {}
        for record in usage_records:
            month_key = record.created_at.strftime('%Y-%m')
            if month_key not in usage_by_month:
                usage_by_month[month_key] = {}
            
            if record.resource_type not in usage_by_month[month_key]:
                usage_by_month[month_key][record.resource_type] = 0
            
            usage_by_month[month_key][record.resource_type] += record.quantity
        
        return {
            'total_paid': total_paid,
            'average_monthly': avg_monthly,
            'payment_count': len(payments),
            'usage_by_month': usage_by_month,
            'period_start': start_date,
            'period_end': datetime.utcnow()
        }
    
    # =============================================================================
    # HELPER METHODS
    # =============================================================================
    
    def _calculate_period_end(self, start_date: datetime, billing_cycle: str) -> datetime:
        """Calculate billing period end date"""
        if billing_cycle == 'monthly':
            return start_date + timedelta(days=30)
        elif billing_cycle == 'annual':
            return start_date + timedelta(days=365)
        else:
            raise ValueError(f"Invalid billing cycle: {billing_cycle}")
    
    def _generate_invoice_number(self) -> str:
        """Generate unique invoice number"""
        timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
        return f"INV-{timestamp}"
    
    def _get_stripe_price_id(self, plan: SubscriptionPlan, billing_cycle: str) -> str:
        """Get Stripe price ID for plan and billing cycle"""
        # This would be stored in plan metadata or separate table
        metadata = plan.sub_plan_metadata or {}
        price_key = f"stripe_price_id_{billing_cycle}"
        return metadata.get(price_key)
    
    def _get_unit_cost(self, plan: SubscriptionPlan, resource_type: str) -> Decimal:
        """Get unit cost for resource type"""
        # For now, return 0 - usage is included in subscription
        # Future: implement usage-based pricing
        return Decimal('0.00')
    
    def _handle_plan_change_proration(self, subscription: Subscription, 
                                    new_plan: SubscriptionPlan, new_amount: Decimal):
        """Handle proration when changing plans"""
        # Calculate proration based on remaining time in period
        now = datetime.utcnow()
        total_period = (subscription.current_period_end - subscription.current_period_start).days
        remaining_days = (subscription.current_period_end - now).days
        
        if remaining_days > 0:
            proration_factor = remaining_days / total_period
            old_remaining = float(subscription.amount) * proration_factor
            new_remaining = float(new_amount) * proration_factor
            proration_amount = new_remaining - old_remaining
            
            self.logger.info(f"Plan change proration: {proration_amount}")
            # TODO: Create proration invoice item if amount > 0