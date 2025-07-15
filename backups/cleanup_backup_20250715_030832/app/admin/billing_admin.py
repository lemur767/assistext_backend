# app/admin/billing_admin.py
"""
Admin tools for billing management
Provides administrative interface for managing subscriptions, invoices, and billing issues
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash
from flask_login import login_required
from sqlalchemy import func, desc, asc
from app.extensions import db
from app.models.user import User
from app.models.subscription import Subscription, SubscriptionPlan
from app.models.payment import Payment, PaymentMethod
from app.models.invoice import Invoice
from app.models.usage import Usage
from app.models.billing_settings import BillingSettings
from app.services.payment_processor import PaymentProcessor
from app.services.invoice_generator import InvoiceGenerator
from app.services.notification_service import NotificationService
from app.utils.decorators import admin_required

logger = logging.getLogger(__name__)

admin_billing_bp = Blueprint('admin_billing', __name__, url_prefix='/admin/billing')

class BillingAdmin:
    """Administrative tools for billing management"""
    
    @staticmethod
    def get_billing_overview() -> Dict[str, Any]:
        """Get comprehensive billing overview for admin dashboard"""
        try:
            # Subscription metrics
            total_subscriptions = Subscription.query.count()
            active_subscriptions = Subscription.query.filter_by(status='active').count()
            trial_subscriptions = Subscription.query.filter_by(status='trialing').count()
            canceled_subscriptions = Subscription.query.filter_by(status='canceled').count()
            
            # Revenue metrics (last 30 days)
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            recent_revenue = db.session.query(func.sum(Payment.amount)).filter(
                Payment.status == 'succeeded',
                Payment.created_at >= thirty_days_ago
            ).scalar() or 0
            
            # Failed payments (last 7 days)
            seven_days_ago = datetime.utcnow() - timedelta(days=7)
            failed_payments = Payment.query.filter(
                Payment.status == 'failed',
                Payment.created_at >= seven_days_ago
            ).count()
            
            # Overdue invoices
            overdue_invoices = Invoice.query.filter(
                Invoice.status == 'open',
                Invoice.due_date < datetime.utcnow()
            ).count()
            
            # Trial conversions (last 30 days)
            converted_trials = Subscription.query.filter(
                Subscription.status == 'active',
                Subscription.trial_end.isnot(None),
                Subscription.trial_end >= thirty_days_ago,
                Subscription.trial_end <= datetime.utcnow()
            ).count()
            
            # MRR calculation
            monthly_subscriptions = Subscription.query.filter(
                Subscription.status == 'active',
                Subscription.billing_cycle == 'monthly'
            ).all()
            
            annual_subscriptions = Subscription.query.filter(
                Subscription.status == 'active',
                Subscription.billing_cycle == 'annual'
            ).all()
            
            mrr = sum(float(sub.amount) for sub in monthly_subscriptions)
            mrr += sum(float(sub.amount) / 12 for sub in annual_subscriptions)
            
            return {
                'subscriptions': {
                    'total': total_subscriptions,
                    'active': active_subscriptions,
                    'trial': trial_subscriptions,
                    'canceled': canceled_subscriptions
                },
                'revenue': {
                    'last_30_days': float(recent_revenue),
                    'mrr': round(mrr, 2),
                    'arr': round(mrr * 12, 2)
                },
                'issues': {
                    'failed_payments': failed_payments,
                    'overdue_invoices': overdue_invoices
                },
                'conversions': {
                    'trial_conversions': converted_trials
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting billing overview: {str(e)}")
            return {}
    
    @staticmethod
    def search_customers(query: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Search customers by email, name, or subscription details"""
        try:
            # Search users
            users_query = User.query.filter(
                db.or_(
                    User.email.ilike(f'%{query}%'),
                    User.first_name.ilike(f'%{query}%'),
                    User.last_name.ilike(f'%{query}%')
                )
            ).limit(limit)
            
            results = []
            for user in users_query:
                # Get subscription info
                subscription = Subscription.query.filter_by(
                    user_id=user.id,
                    status__in=['active', 'trialing', 'past_due']
                ).first()
                
                # Get payment info
                latest_payment = Payment.query.filter_by(user_id=user.id).order_by(
                    desc(Payment.created_at)
                ).first()
                
                results.append({
                    'user': user.to_dict(),
                    'subscription': subscription.to_dict() if subscription else None,
                    'latest_payment': latest_payment.to_dict() if latest_payment else None
                })
            
            return results
            
        except Exception as e:
            logger.error(f"Error searching customers: {str(e)}")
            return []
    
    @staticmethod
    def get_customer_billing_details(user_id: str) -> Dict[str, Any]:
        """Get comprehensive billing details for a specific customer"""
        try:
            user = User.query.get(user_id)
            if not user:
                return {'error': 'User not found'}
            
            # Get subscription
            subscription = Subscription.query.filter_by(user_id=user_id).order_by(
                desc(Subscription.created_at)
            ).first()
            
            # Get payment methods
            payment_methods = PaymentMethod.query.filter_by(
                user_id=user_id,
                status='active'
            ).all()
            
            # Get invoices
            invoices = Invoice.query.filter_by(user_id=user_id).order_by(
                desc(Invoice.created_at)
            ).limit(10).all()
            
            # Get payments
            payments = Payment.query.filter_by(user_id=user_id).order_by(
                desc(Payment.created_at)
            ).limit(10).all()
            
            # Get usage
            current_usage = None
            if subscription:
                current_usage = Usage.query.filter_by(
                    subscription_id=subscription.id
                ).order_by(desc(Usage.created_at)).first()
            
            # Get billing settings
            billing_settings = BillingSettings.query.filter_by(user_id=user_id).first()
            
            return {
                'user': user.to_dict(),
                'subscription': subscription.to_dict(include_relationships=True) if subscription else None,
                'payment_methods': [pm.to_dict() for pm in payment_methods],
                'invoices': [inv.to_dict() for inv in invoices],
                'payments': [pay.to_dict() for pay in payments],
                'usage': current_usage.to_dict() if current_usage else None,
                'billing_settings': billing_settings.to_dict() if billing_settings else None
            }
            
        except Exception as e:
            logger.error(f"Error getting customer billing details: {str(e)}")
            return {'error': str(e)}
    
    @staticmethod
    def apply_billing_adjustment(user_id: str, adjustment_type: str, amount: float, 
                               reason: str, description: str = None) -> Dict[str, Any]:
        """Apply billing adjustment (credit, debit, refund, etc.)"""
        try:
            user = User.query.get(user_id)
            if not user:
                return {'success': False, 'error': 'User not found'}
            
            # Create credit transaction
            from app.models.credit_transaction import CreditTransaction
            
            # Get current balance
            latest_transaction = CreditTransaction.query.filter_by(
                user_id=user_id
            ).order_by(desc(CreditTransaction.created_at)).first()
            
            current_balance = latest_transaction.balance_after if latest_transaction else 0.0
            
            # Calculate new balance
            if adjustment_type in ['credit', 'refund', 'bonus']:
                new_balance = current_balance + amount
            else:  # debit, adjustment
                new_balance = current_balance - amount
            
            # Create transaction record
            transaction = CreditTransaction(
                user_id=user_id,
                type=adjustment_type,
                amount=amount,
                balance_after=new_balance,
                description=description or f"Admin {adjustment_type}: {reason}",
                reference_type='admin_adjustment',
                processed_at=datetime.utcnow(),
                metadata={
                    'admin_reason': reason,
                    'admin_user': 'system',  # You might want to track which admin user did this
                    'adjustment_date': datetime.utcnow().isoformat()
                }
            )
            
            db.session.add(transaction)
            db.session.commit()
            
            # Send notification to user
            NotificationService.send_billing_adjustment_notification(
                user_id, adjustment_type, amount, reason
            )
            
            logger.info(f"Applied {adjustment_type} of ${amount} to user {user_id}: {reason}")
            
            return {
                'success': True,
                'transaction_id': transaction.id,
                'new_balance': new_balance,
                'message': f'{adjustment_type.title()} applied successfully'
            }
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error applying billing adjustment: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def force_invoice_payment(invoice_id: str, admin_note: str = None) -> Dict[str, Any]:
        """Force mark an invoice as paid (admin override)"""
        try:
            invoice = Invoice.query.get(invoice_id)
            if not invoice:
                return {'success': False, 'error': 'Invoice not found'}
            
            if invoice.status == 'paid':
                return {'success': False, 'error': 'Invoice already paid'}
            
            # Create admin payment record
            from app.models.payment import Payment
            import uuid
            
            admin_payment = Payment(
                id=str(uuid.uuid4()),
                user_id=invoice.user_id,
                invoice_id=invoice_id,
                amount=invoice.amount_due,
                currency=invoice.currency,
                status='succeeded',
                description=f"Admin override payment: {admin_note or 'No note provided'}",
                processed_at=datetime.utcnow(),
                metadata={
                    'admin_override': True,
                    'admin_note': admin_note,
                    'override_date': datetime.utcnow().isoformat()
                }
            )
            
            # Update invoice
            invoice.status = 'paid'
            invoice.amount_paid = invoice.total
            invoice.amount_due = 0.0
            invoice.paid_at = datetime.utcnow()
            
            db.session.add(admin_payment)
            db.session.commit()
            
            # Send notification
            NotificationService.send_invoice_notification(invoice.user_id, invoice_id, 'paid')
            
            logger.info(f"Admin force-paid invoice {invoice.invoice_number}")
            
            return {
                'success': True,
                'payment_id': admin_payment.id,
                'message': 'Invoice marked as paid'
            }
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error force-paying invoice: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def cancel_subscription_with_refund(subscription_id: str, refund_amount: float = None, 
                                      reason: str = None) -> Dict[str, Any]:
        """Cancel subscription and process refund"""
        try:
            subscription = Subscription.query.get(subscription_id)
            if not subscription:
                return {'success': False, 'error': 'Subscription not found'}
            
            if subscription.status in ['canceled', 'expired']:
                return {'success': False, 'error': 'Subscription already canceled'}
            
            # Get latest payment for refund calculation
            latest_payment = Payment.query.filter_by(
                subscription_id=subscription_id,
                status='succeeded'
            ).order_by(desc(Payment.created_at)).first()
            
            # Calculate refund amount if not provided
            if refund_amount is None and latest_payment:
                # Calculate prorated refund
                days_in_period = (subscription.current_period_end - subscription.current_period_start).days
                days_remaining = (subscription.current_period_end - datetime.utcnow()).days
                
                if days_remaining > 0:
                    refund_amount = (float(latest_payment.amount) * days_remaining) / days_in_period
                else:
                    refund_amount = 0.0
            
            # Cancel subscription
            subscription.status = 'canceled'
            subscription.canceled_at = datetime.utcnow()
            subscription.cancellation_reason = reason or 'Admin cancellation with refund'
            
            # Process refund if amount > 0
            refund_result = None
            if refund_amount and refund_amount > 0 and latest_payment:
                refund_result = PaymentProcessor.refund_payment(
                    latest_payment.stripe_payment_intent_id,
                    refund_amount,
                    reason or 'Admin refund'
                )
            
            db.session.commit()
            
            # Send notifications
            NotificationService.send_subscription_notification(
                subscription.user_id, subscription_id, 'canceled'
            )
            
            if refund_result and refund_result['success']:
                NotificationService.send_payment_notification(
                    subscription.user_id, latest_payment.id, 'refunded'
                )
            
            logger.info(f"Admin canceled subscription {subscription_id} with refund ${refund_amount}")
            
            return {
                'success': True,
                'refund_amount': refund_amount,
                'refund_result': refund_result,
                'message': 'Subscription canceled and refund processed'
            }
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error canceling subscription with refund: {str(e)}")
            return {'success': False, 'error': str(e)}


# Flask routes for admin interface
@admin_billing_bp.route('/dashboard')
@login_required
@admin_required
def admin_dashboard():
    """Admin billing dashboard"""
    overview = BillingAdmin.get_billing_overview()
    return render_template('admin/billing_dashboard.html', overview=overview)

@admin_billing_bp.route('/customers/search')
@login_required
@admin_required
def search_customers():
    """Search customers"""
    query = request.args.get('q', '')
    if not query:
        return jsonify({'error': 'Search query required'}), 400
    
    results = BillingAdmin.search_customers(query)
    return jsonify({'customers': results})

@admin_billing_bp.route('/customers/<user_id>')
@login_required
@admin_required
def customer_details(user_id):
    """Get customer billing details"""
    details = BillingAdmin.get_customer_billing_details(user_id)
    if 'error' in details:
        flash(details['error'], 'error')
        return redirect(url_for('admin_billing.admin_dashboard'))
    
    return render_template('admin/customer_details.html', customer=details)

@admin_billing_bp.route('/adjustments', methods=['POST'])
@login_required
@admin_required
def apply_adjustment():
    """Apply billing adjustment"""
    data = request.json
    
    result = BillingAdmin.apply_billing_adjustment(
        user_id=data['user_id'],
        adjustment_type=data['type'],
        amount=float(data['amount']),
        reason=data['reason'],
        description=data.get('description')
    )
    
    return jsonify(result)

@admin_billing_bp.route('/invoices/<invoice_id>/force-pay', methods=['POST'])
@login_required
@admin_required
def force_pay_invoice(invoice_id):
    """Force pay invoice"""
    data = request.json or {}
    admin_note = data.get('note', '')
    
    result = BillingAdmin.force_invoice_payment(invoice_id, admin_note)
    return jsonify(result)

@admin_billing_bp.route('/subscriptions/<subscription_id>/cancel-refund', methods=['POST'])
@login_required
@admin_required
def cancel_with_refund(subscription_id):
    """Cancel subscription with refund"""
    data = request.json or {}
    
    result = BillingAdmin.cancel_subscription_with_refund(
        subscription_id=subscription_id,
        refund_amount=data.get('refund_amount'),
        reason=data.get('reason')
    )
    
    return jsonify(result)