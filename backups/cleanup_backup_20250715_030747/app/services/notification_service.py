# app/services/notification_service.py
"""
Notification service for billing events and usage alerts
Handles email notifications, in-app notifications, and webhook delivery
"""

import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from flask import current_app, render_template, url_for
from flask_mail import Message as EmailMessage

from app.extensions import db, mail
from app.models.user import User
from app.models.invoice import Invoice
from app.models.subscription import Subscription
from app.models.billing_settings import BillingSettings

logger = logging.getLogger(__name__)

class NotificationService:
    """Service for handling billing and usage notifications"""
    
    @classmethod
    def send_invoice_notification(cls, user_id: str, invoice_id: str, event_type: str) -> Dict[str, Any]:
        """Send invoice-related notifications"""
        try:
            user = User.query.get(user_id)
            invoice = Invoice.query.get(invoice_id)
            
            if not user or not invoice:
                return {'success': False, 'error': 'User or invoice not found'}
            
            # Check notification preferences
            billing_settings = BillingSettings.query.filter_by(user_id=user_id).first()
            if billing_settings and not billing_settings.notifications.get('invoice_created', True):
                return {'success': True, 'message': 'Notification disabled by user'}
            
            # Determine email template and subject based on event type
            templates = {
                'created': {
                    'subject': f'Invoice {invoice.invoice_number} - ${invoice.total:.2f}',
                    'template': 'emails/invoice_created.html'
                },
                'paid': {
                    'subject': f'Payment Received - Invoice {invoice.invoice_number}',
                    'template': 'emails/invoice_paid.html'
                },
                'overdue': {
                    'subject': f'Invoice Overdue - {invoice.invoice_number}',
                    'template': 'emails/invoice_overdue.html'
                }
            }
            
            template_info = templates.get(event_type)
            if not template_info:
                return {'success': False, 'error': f'Unknown event type: {event_type}'}
            
            # Prepare email data
            email_data = {
                'user': user,
                'invoice': invoice,
                'invoice_url': url_for('billing.get_invoice', invoice_id=invoice_id, _external=True),
                'dashboard_url': url_for('dashboard.billing', _external=True),
                'company_name': current_app.config.get('COMPANY_NAME', 'AssisText'),
                'support_email': current_app.config.get('SUPPORT_EMAIL', 'support@assistext.com')
            }
            
            # Send email
            cls._send_email(
                to=user.email,
                subject=template_info['subject'],
                template=template_info['template'],
                data=email_data
            )
            
            logger.info(f"Sent {event_type} invoice notification to {user.email}")
            
            return {'success': True, 'message': 'Notification sent successfully'}
            
        except Exception as e:
            logger.error(f"Error sending invoice notification: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @classmethod
    def send_payment_notification(cls, user_id: str, payment_id: str, event_type: str) -> Dict[str, Any]:
        """Send payment-related notifications"""
        try:
            user = User.query.get(user_id)
            if not user:
                return {'success': False, 'error': 'User not found'}
            
            # Check notification preferences
            billing_settings = BillingSettings.query.filter_by(user_id=user_id).first()
            notification_key = f'payment_{event_type}'
            
            if billing_settings and not billing_settings.notifications.get(notification_key, True):
                return {'success': True, 'message': 'Notification disabled by user'}
            
            # Get payment details
            from app.models.payment import Payment
            payment = Payment.query.get(payment_id)
            if not payment:
                return {'success': False, 'error': 'Payment not found'}
            
            # Determine email template
            templates = {
                'succeeded': {
                    'subject': f'Payment Confirmation - ${payment.amount:.2f}',
                    'template': 'emails/payment_succeeded.html'
                },
                'failed': {
                    'subject': 'Payment Failed - Action Required',
                    'template': 'emails/payment_failed.html'
                },
                'refunded': {
                    'subject': f'Refund Processed - ${payment.refunded_amount:.2f}',
                    'template': 'emails/payment_refunded.html'
                }
            }
            
            template_info = templates.get(event_type)
            if not template_info:
                return {'success': False, 'error': f'Unknown event type: {event_type}'}
            
            # Prepare email data
            email_data = {
                'user': user,
                'payment': payment,
                'dashboard_url': url_for('dashboard.billing', _external=True),
                'support_url': url_for('support.contact', _external=True),
                'company_name': current_app.config.get('COMPANY_NAME', 'AssisText')
            }
            
            # Send email
            cls._send_email(
                to=user.email,
                subject=template_info['subject'],
                template=template_info['template'],
                data=email_data
            )
            
            logger.info(f"Sent {event_type} payment notification to {user.email}")
            
            return {'success': True, 'message': 'Notification sent successfully'}
            
        except Exception as e:
            logger.error(f"Error sending payment notification: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @classmethod
    def send_subscription_notification(cls, user_id: str, subscription_id: str, event_type: str) -> Dict[str, Any]:
        """Send subscription-related notifications"""
        try:
            user = User.query.get(user_id)
            subscription = Subscription.query.get(subscription_id)
            
            if not user or not subscription:
                return {'success': False, 'error': 'User or subscription not found'}
            
            # Check notification preferences
            billing_settings = BillingSettings.query.filter_by(user_id=user_id).first()
            notification_key = f'subscription_{event_type}'
            
            if billing_settings and not billing_settings.notifications.get(notification_key, True):
                return {'success': True, 'message': 'Notification disabled by user'}
            
            # Determine email template
            templates = {
                'created': {
                    'subject': f'Welcome to {subscription.plan.name}!',
                    'template': 'emails/subscription_created.html'
                },
                'renewed': {
                    'subject': f'Subscription Renewed - {subscription.plan.name}',
                    'template': 'emails/subscription_renewed.html'
                },
                'canceled': {
                    'subject': 'Subscription Canceled',
                    'template': 'emails/subscription_canceled.html'
                },
                'trial_ending': {
                    'subject': 'Trial Ending Soon - Action Required',
                    'template': 'emails/trial_ending.html'
                }
            }
            
            template_info = templates.get(event_type)
            if not template_info:
                return {'success': False, 'error': f'Unknown event type: {event_type}'}
            
            # Prepare email data
            email_data = {
                'user': user,
                'subscription': subscription,
                'plan': subscription.plan,
                'dashboard_url': url_for('dashboard.subscription', _external=True),
                'billing_url': url_for('dashboard.billing', _external=True),
                'company_name': current_app.config.get('COMPANY_NAME', 'AssisText')
            }
            
            # Send email
            cls._send_email(
                to=user.email,
                subject=template_info['subject'],
                template=template_info['template'],
                data=email_data
            )
            
            logger.info(f"Sent {event_type} subscription notification to {user.email}")
            
            return {'success': True, 'message': 'Notification sent successfully'}
            
        except Exception as e:
            logger.error(f"Error sending subscription notification: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @classmethod
    def send_usage_alert(cls, user_id: str, alert_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Send usage alert notifications"""
        try:
            user = User.query.get(user_id)
            if not user:
                return {'success': False, 'error': 'User not found'}
            
            # Check notification preferences
            billing_settings = BillingSettings.query.filter_by(user_id=user_id).first()
            if billing_settings and not billing_settings.notifications.get('usage_alerts', True):
                return {'success': True, 'message': 'Usage alerts disabled by user'}
            
            # Determine email template
            templates = {
                'sms_limit_warning': {
                    'subject': 'SMS Credits Running Low',
                    'template': 'emails/usage_warning.html'
                },
                'ai_limit_warning': {
                    'subject': 'AI Credits Running Low',
                    'template': 'emails/usage_warning.html'
                },
                'storage_limit_warning': {
                    'subject': 'Storage Limit Warning',
                    'template': 'emails/usage_warning.html'
                },
                'sms_overage': {
                    'subject': 'SMS Overage Charges Applied',
                    'template': 'emails/usage_overage.html'
                },
                'ai_overage': {
                    'subject': 'AI Overage Charges Applied',
                    'template': 'emails/usage_overage.html'
                }
            }
            
            template_info = templates.get(alert_type)
            if not template_info:
                return {'success': False, 'error': f'Unknown alert type: {alert_type}'}
            
            # Prepare email data
            email_data = {
                'user': user,
                'alert_type': alert_type,
                'alert_data': data,
                'dashboard_url': url_for('dashboard.usage', _external=True),
                'upgrade_url': url_for('dashboard.subscription', _external=True),
                'company_name': current_app.config.get('COMPANY_NAME', 'AssisText')
            }
            
            # Send email
            cls._send_email(
                to=user.email,
                subject=template_info['subject'],
                template=template_info['template'],
                data=email_data
            )
            
            logger.info(f"Sent {alert_type} usage alert to {user.email}")
            
            return {'success': True, 'message': 'Usage alert sent successfully'}
            
        except Exception as e:
            logger.error(f"Error sending usage alert: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @classmethod
    def send_trial_notifications(cls) -> Dict[str, Any]:
        """Send trial ending notifications (called by cron job)"""
        try:
            # Find subscriptions with trials ending in 3 days
            trial_ending_date = datetime.utcnow() + timedelta(days=3)
            
            subscriptions = Subscription.query.filter(
                Subscription.status == 'trialing',
                Subscription.trial_end <= trial_ending_date,
                Subscription.trial_end >= datetime.utcnow()
            ).all()
            
            notifications_sent = 0
            
            for subscription in subscriptions:
                # Check if we already sent a trial ending notification
                # (You might want to track this in a separate table)
                
                result = cls.send_subscription_notification(
                    subscription.user_id,
                    subscription.id,
                    'trial_ending'
                )
                
                if result['success']:
                    notifications_sent += 1
            
            logger.info(f"Sent {notifications_sent} trial ending notifications")
            
            return {
                'success': True,
                'notifications_sent': notifications_sent,
                'message': f'Sent {notifications_sent} trial ending notifications'
            }
            
        except Exception as e:
            logger.error(f"Error sending trial notifications: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @classmethod
    def send_overdue_invoice_notifications(cls) -> Dict[str, Any]:
        """Send overdue invoice notifications (called by cron job)"""
        try:
            # Find overdue invoices
            overdue_invoices = Invoice.query.filter(
                Invoice.status == 'open',
                Invoice.due_date < datetime.utcnow(),
                Invoice.amount_due > 0
            ).all()
            
            notifications_sent = 0
            
            for invoice in overdue_invoices:
                result = cls.send_invoice_notification(
                    invoice.user_id,
                    invoice.id,
                    'overdue'
                )
                
                if result['success']:
                    notifications_sent += 1
            
            logger.info(f"Sent {notifications_sent} overdue invoice notifications")
            
            return {
                'success': True,
                'notifications_sent': notifications_sent,
                'message': f'Sent {notifications_sent} overdue notifications'
            }
            
        except Exception as e:
            logger.error(f"Error sending overdue notifications: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    # Private helper methods
    
    @classmethod
    def _send_email(cls, to: str, subject: str, template: str, data: Dict[str, Any]):
        """Send email using Flask-Mail"""
        try:
            msg = EmailMessage(
                subject=subject,
                recipients=[to],
                sender=current_app.config.get('MAIL_DEFAULT_SENDER')
            )
            
            # Render HTML template
            msg.html = render_template(template, **data)
            
            # Send email
            mail.send(msg)
            
        except Exception as e:
            logger.error(f"Error sending email to {to}: {str(e)}")
            raise


# Celery task for scheduled notifications
def schedule_billing_notifications():
    """Celery task to send scheduled billing notifications"""
    try:
        # Send trial ending notifications
        NotificationService.send_trial_notifications()
        
        # Send overdue invoice notifications
        NotificationService.send_overdue_invoice_notifications()
        
        logger.info("Completed scheduled billing notifications")
        
    except Exception as e:
        logger.error(f"Error in scheduled billing notifications: {str(e)}")


# Flask CLI command for manual notification sending
def init_notification_commands(app):
    """Initialize CLI commands for notifications"""
    
    @app.cli.command('send-trial-notifications')
    def send_trial_notifications_command():
        """Send trial ending notifications"""
        result = NotificationService.send_trial_notifications()
        print(f"Result: {result}")
    
    @app.cli.command('send-overdue-notifications')
    def send_overdue_notifications_command():
        """Send overdue invoice notifications"""
        result = NotificationService.send_overdue_invoice_notifications()
        print(f"Result: {result}")