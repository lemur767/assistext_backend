# app/utils/billing_helpers.py
"""
Utility functions for billing operations
"""

from datetime import datetime, timedelta
from typing import Dict, List, Any
from app.models.subscription import Subscription, SubscriptionPlan
from app.models.payment import Payment
from app.models.invoice import Invoice
from app.models.usage import Usage
from app.extensions import db
from sqlalchemy import func

class BillingHelpers:
    """Helper functions for billing operations"""
    
    @staticmethod
    def calculate_proration(subscription: Subscription, new_plan: SubscriptionPlan, 
                          new_billing_cycle: str) -> Dict[str, Any]:
        """Calculate proration for plan changes"""
        
        # Get current period info
        current_period_days = (subscription.current_period_end - subscription.current_period_start).days
        days_used = (datetime.utcnow() - subscription.current_period_start).days
        days_remaining = current_period_days - days_used
        
        # Calculate current plan daily rate
        current_amount = subscription.amount
        current_daily_rate = current_amount / current_period_days
        
        # Calculate new plan amount
        new_amount = new_plan.monthly_price if new_billing_cycle == 'monthly' else new_plan.annual_price
        new_daily_rate = new_amount / (30 if new_billing_cycle == 'monthly' else 365)
        
        # Calculate proration
        unused_amount = current_daily_rate * days_remaining
        new_period_amount = new_daily_rate * days_remaining
        proration_amount = new_period_amount - unused_amount
        
        return {
            'current_amount': current_amount,
            'new_amount': new_amount,
            'proration_amount': proration_amount,
            'days_remaining': days_remaining,
            'effective_date': datetime.utcnow(),
            'next_billing_date': subscription.current_period_end
        }
    
    @staticmethod
    def validate_coupon(coupon_code: str, plan_id: str = None) -> Dict[str, Any]:
        """Validate coupon code"""
        # This is a simplified validation
        # In production, you'd integrate with your coupon system
        
        valid_coupons = {
            'WELCOME10': {'valid': True, 'discount_percentage': 10, 'discount_amount': None},
            'SAVE20': {'valid': True, 'discount_percentage': 20, 'discount_amount': None},
            'FLAT50': {'valid': True, 'discount_percentage': None, 'discount_amount': 50.0}
        }
        
        coupon = valid_coupons.get(coupon_code.upper())
        
        if coupon:
            # Apply plan-specific restrictions if needed
            if plan_id:
                # Check if coupon is valid for this plan
                pass
            
            return {
                'valid': True,
                'discount_percentage': coupon['discount_percentage'],
                'discount_amount': coupon['discount_amount'],
                'expires_at': (datetime.utcnow() + timedelta(days=30)).isoformat()
            }
        
        return {'valid': False}
    
    @staticmethod
    def calculate_tax(amount: float, billing_address: Dict[str, str]) -> Dict[str, Any]:
        """Calculate tax based on billing address"""
        # Simplified tax calculation
        # In production, you'd integrate with a tax service like TaxJar or Avalara
        
        tax_rates = {
            'CA': 0.08,  # California
            'NY': 0.08,  # New York
            'TX': 0.06,  # Texas
            'FL': 0.06,  # Florida
        }
        
        state = billing_address.get('state', '').upper()
        tax_rate = tax_rates.get(state, 0.0)
        tax_amount = amount * tax_rate
        
        return {
            'tax_amount': round(tax_amount, 2),
            'tax_rate': tax_rate,
            'tax_name': f"{state} Sales Tax" if tax_rate > 0 else None
        }
    
    @staticmethod
    def generate_analytics(user_id: str, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Generate billing analytics for user"""
        
        # Get subscription data
        subscriptions = Subscription.query.filter_by(user_id=user_id).all()
        
        # Get payment data
        payments = Payment.query.filter(
            Payment.user_id == user_id,
            Payment.created_at >= start_date,
            Payment.created_at <= end_date
        ).all()
        
        # Calculate metrics
        total_revenue = sum(p.amount for p in payments if p.status == 'succeeded')
        total_refunds = sum(p.refunded_amount or 0 for p in payments)
        net_revenue = total_revenue - total_refunds
        
        # Get current subscription for MRR
        current_subscription = next((s for s in subscriptions if s.status in ['active', 'trialing']), None)
        mrr = current_subscription.amount if current_subscription and current_subscription.billing_cycle == 'monthly' else 0
        arr = mrr * 12
        
        # Payment success rate
        total_payment_attempts = len(payments)
        successful_payments = len([p for p in payments if p.status == 'succeeded'])
        payment_success_rate = (successful_payments / total_payment_attempts * 100) if total_payment_attempts > 0 else 100
        
        return {
            'total_revenue': round(total_revenue, 2),
            'subscription_revenue': round(total_revenue, 2),  # Assuming all revenue is subscription-based
            'usage_revenue': 0.0,  # TODO: Calculate usage-based revenue
            'total_refunds': round(total_refunds, 2),
            'net_revenue': round(net_revenue, 2),
            'mrr': round(mrr, 2),
            'arr': round(arr, 2),
            'payment_success_rate': round(payment_success_rate, 2),
            'new_subscriptions': len([s for s in subscriptions if s.created_at >= start_date]),
            'canceled_subscriptions': len([s for s in subscriptions if s.canceled_at and s.canceled_at >= start_date]),
            'churn_rate': 0.0,  # TODO: Calculate churn rate
            'customer_lifetime_value': 0.0,  # TODO: Calculate CLV
        }
    
    @staticmethod
    def generate_export_data(user_id: str, export_type: str, start_date: str = None, 
                           end_date: str = None) -> List[Dict[str, Any]]:
        """Generate export data for billing information"""
        
        if start_date:
            start_date = datetime.fromisoformat(start_date)
        if end_date:
            end_date = datetime.fromisoformat(end_date)
        
        if export_type == 'invoices':
            query = Invoice.query.filter_by(user_id=user_id)
            if start_date:
                query = query.filter(Invoice.created_at >= start_date)
            if end_date:
                query = query.filter(Invoice.created_at <= end_date)
            
            invoices = query.all()
            return [{
                'invoice_number': inv.invoice_number,
                'date': inv.created_at.isoformat(),
                'status': inv.status,
                'subtotal': inv.subtotal,
                'tax': inv.tax_amount,
                'total': inv.total,
                'currency': inv.currency,
                'due_date': inv.due_date.isoformat() if inv.due_date else None,
                'paid_date': inv.paid_at.isoformat() if inv.paid_at else None
            } for inv in invoices]
        
        elif export_type == 'payments':
            query = Payment.query.filter_by(user_id=user_id)
            if start_date:
                query = query.filter(Payment.created_at >= start_date)
            if end_date:
                query = query.filter(Payment.created_at <= end_date)
            
            payments = query.all()
            return [{
                'id': payment.id,
                'date': payment.created_at.isoformat(),
                'amount': payment.amount,
                'currency': payment.currency,
                'status': payment.status,
                'description': payment.description,
                'refunded_amount': payment.refunded_amount or 0
            } for payment in payments]
        
        elif export_type == 'subscriptions':
            subscriptions = Subscription.query.filter_by(user_id=user_id).all()
            return [{
                'id': sub.id,
                'plan_name': sub.plan.name if sub.plan else 'Unknown',
                'status': sub.status,
                'billing_cycle': sub.billing_cycle,
                'amount': sub.amount,
                'currency': sub.currency,
                'created_date': sub.created_at.isoformat(),
                'current_period_start': sub.current_period_start.isoformat() if sub.current_period_start else None,
                'current_period_end': sub.current_period_end.isoformat() if sub.current_period_end else None,
                'canceled_date': sub.canceled_at.isoformat() if sub.canceled_at else None
            } for sub in subscriptions]
        
        return []
    
    @staticmethod
    def check_usage_limits(subscription_id: str) -> Dict[str, Any]:
        """Check if subscription is approaching or exceeding usage limits"""
        
        subscription = Subscription.query.get(subscription_id)
        if not subscription:
            return {'error': 'Subscription not found'}
        
        # Get current usage
        usage = Usage.query.filter_by(
            subscription_id=subscription_id,
            period_start__lte=datetime.utcnow(),
            period_end__gte=datetime.utcnow()
        ).first()
        
        if not usage:
            return {'error': 'Usage data not found'}
        
        # Get plan limits
        plan_features = subscription.plan.features
        
        # Check each limit
        limits_status = {
            'sms_credits': {
                'used': usage.sms_credits_used,
                'limit': plan_features.get('sms_credits_monthly', 0),
                'percentage': (usage.sms_credits_used / plan_features.get('sms_credits_monthly', 1)) * 100,
                'exceeded': usage.sms_credits_used >= plan_features.get('sms_credits_monthly', 0)
            },
            'ai_responses': {
                'used': usage.ai_responses_generated,
                'limit': plan_features.get('ai_responses_monthly', 0),
                'percentage': (usage.ai_responses_generated / plan_features.get('ai_responses_monthly', 1)) * 100,
                'exceeded': usage.ai_responses_generated >= plan_features.get('ai_responses_monthly', 0)
            },
            'storage': {
                'used': usage.storage_used_gb,
                'limit': plan_features.get('storage_gb', 0),
                'percentage': (usage.storage_used_gb / plan_features.get('storage_gb', 1)) * 100,
                'exceeded': usage.storage_used_gb >= plan_features.get('storage_gb', 0)
            }
        }
        
        return {
            'subscription_id': subscription_id,
            'limits_status': limits_status,
            'any_exceeded': any(limit['exceeded'] for limit in limits_status.values()),
            'warnings': [name for name, limit in limits_status.items() if limit['percentage'] >= 80 and not limit['exceeded']]
        }