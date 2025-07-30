"""
Email Tasks for Trial Management and User Communications
Handles welcome emails, trial warnings, and subscription notifications
"""

from celery import Celery
from flask import current_app, render_template
from flask_mail import Message
from datetime import datetime, timedelta
from app.extensions import Mail, db
from app.models.user import User
from app.models.subscription import Subscription, SubscriptionPlan
import logging

logger = logging.getLogger(__name__)

# Initialize Celery (adjust this based on your Celery setup)
celery = Celery('email_tasks')

# =============================================================================
# WELCOME EMAILS
# =============================================================================

@celery.task(bind=True, max_retries=3)
def send_welcome_email(self, user_id, email, first_name, username):
    """
    Send welcome email after successful registration
    Called immediately after user registration
    """
    try:
        # Email data for template
        email_data = {
            'first_name': first_name,
            'username': username,
            'login_url': f"{current_app.config.get('FRONTEND_URL', 'https://app.assistext.com')}/login",
            'dashboard_url': f"{current_app.config.get('FRONTEND_URL', 'https://app.assistext.com')}/dashboard",
            'support_email': current_app.config.get('SUPPORT_EMAIL', 'support@assistext.com'),
            'company_name': 'AssisText',
            'current_year': datetime.now().year
        }
        
        # Send welcome email
        _send_email_with_template(
            to_email=email,
            subject=f"Welcome to AssisText, {first_name}!",
            template='emails/welcome_email.html',
            email_data=email_data
        )
        
        logger.info(f"✅ Welcome email sent to user {user_id} ({email})")
        
        return {
            'success': True,
            'user_id': user_id,
            'email': email,
            'email_type': 'welcome',
            'sent_at': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to send welcome email to user {user_id}: {e}")
        
        # Retry with exponential backoff
        if self.request.retries < self.max_retries:
            retry_delay = 2 ** self.request.retries * 60  # 1, 2, 4 minutes
            raise self.retry(countdown=retry_delay, exc=e)
        
        return {'success': False, 'error': str(e)}

@celery.task(bind=True, max_retries=3)
def send_trial_setup_reminder(self, user_id, email, first_name):
    """
    Send reminder to complete trial setup (add payment method)
    Called 24 hours after registration if no payment method added
    """
    try:
        user = User.query.get(user_id)
        if not user or user.trial_status != 'pending_payment':
            logger.info(f"Skipping trial setup reminder - user {user_id} status changed")
            return {'success': True, 'skipped': True}
        
        email_data = {
            'first_name': first_name,
            'setup_url': f"{current_app.config.get('FRONTEND_URL')}/dashboard/billing",
            'trial_duration': '14 days',
            'features_list': [
                'Dedicated phone number',
                'AI-powered SMS responses',
                'Unlimited message processing',
                'Real-time dashboard',
                'Full customer management'
            ],
            'support_email': current_app.config.get('SUPPORT_EMAIL'),
            'company_name': 'AssisText'
        }
        
        _send_email_with_template(
            to_email=email,
            subject="Complete Your AssisText Trial Setup",
            template='emails/trial_setup_reminder.html',
            email_data=email_data
        )
        
        logger.info(f"✅ Trial setup reminder sent to user {user_id}")
        
        return {
            'success': True,
            'user_id': user_id,
            'email_type': 'trial_setup_reminder',
            'sent_at': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to send trial setup reminder to user {user_id}: {e}")
        
        if self.request.retries < self.max_retries:
            retry_delay = 2 ** self.request.retries * 60
            raise self.retry(countdown=retry_delay, exc=e)
        
        return {'success': False, 'error': str(e)}

# =============================================================================
# TRIAL WARNING EMAILS
# =============================================================================

@celery.task(bind=True, max_retries=3)
def send_trial_warning_email(self, user_id, email, first_name, days_remaining, phone_number=None):
    """
    Send trial expiration warning email
    Called at 7, 3, and 1 days before trial expiry
    """
    try:
        user = User.query.get(user_id)
        if not user or user.trial_status != 'active':
            logger.info(f"Skipping trial warning - user {user_id} status changed")
            return {'success': True, 'skipped': True}
        
        # Determine urgency level and messaging
        if days_remaining >= 7:
            urgency = 'early'
            subject = f"Your AssisText Trial - {days_remaining} Days Remaining"
        elif days_remaining >= 3:
            urgency = 'medium'
            subject = f"Action Needed: {days_remaining} Days Left in Your Trial"
        else:
            urgency = 'urgent'
            subject = f"🚨 URGENT: Only {days_remaining} Day{'s' if days_remaining > 1 else ''} Left!"
        
        email_data = {
            'first_name': first_name,
            'days_remaining': days_remaining,
            'urgency_level': urgency,
            'trial_end_date': user.trial_end_date.strftime('%B %d, %Y') if user.trial_end_date else 'Soon',
            'phone_number': phone_number,
            'upgrade_url': f"{current_app.config.get('FRONTEND_URL')}/dashboard/billing",
            'dashboard_url': f"{current_app.config.get('FRONTEND_URL')}/dashboard",
            'usage_stats': _get_trial_usage_stats(user_id),
            'support_email': current_app.config.get('SUPPORT_EMAIL'),
            'company_name': 'AssisText'
        }
        
        _send_email_with_template(
            to_email=email,
            subject=subject,
            template='emails/trial_warning.html',
            email_data=email_data
        )
        
        logger.info(f"✅ {days_remaining}-day trial warning sent to user {user_id}")
        
        return {
            'success': True,
            'user_id': user_id,
            'days_remaining': days_remaining,
            'urgency_level': urgency,
            'email_type': 'trial_warning',
            'sent_at': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to send trial warning to user {user_id}: {e}")
        
        if self.request.retries < self.max_retries:
            retry_delay = 2 ** self.request.retries * 60
            raise self.retry(countdown=retry_delay, exc=e)
        
        return {'success': False, 'error': str(e)}

@celery.task(bind=True, max_retries=3)
def send_trial_expired_email(self, user_id, email, first_name, phone_number=None):
    """
    Send trial expiration notice
    Called when trial expires and services are suspended
    """
    try:
        user = User.query.get(user_id)
        if not user:
            return {'success': False, 'error': 'User not found'}
        
        email_data = {
            'first_name': first_name,
            'phone_number': phone_number,
            'reactivate_url': f"{current_app.config.get('FRONTEND_URL')}/dashboard/billing",
            'trial_duration': '14 days',
            'grace_period_hours': 24,  # If you have a grace period
            'support_email': current_app.config.get('SUPPORT_EMAIL'),
            'company_name': 'AssisText',
            'trial_stats': _get_trial_usage_stats(user_id)
        }
        
        _send_email_with_template(
            to_email=email,
            subject="🚨 AssisText Trial Expired - Reactivate Your Service",
            template='emails/trial_expired.html',
            email_data=email_data
        )
        
        logger.info(f"✅ Trial expired email sent to user {user_id}")
        
        return {
            'success': True,
            'user_id': user_id,
            'email_type': 'trial_expired',
            'sent_at': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to send trial expired email to user {user_id}: {e}")
        
        if self.request.retries < self.max_retries:
            retry_delay = 2 ** self.request.retries * 60
            raise self.retry(countdown=retry_delay, exc=e)
        
        return {'success': False, 'error': str(e)}

# =============================================================================
# SUBSCRIPTION EMAILS
# =============================================================================

@celery.task(bind=True, max_retries=3)
def send_subscription_welcome_email(self, user_id, email, first_name, phone_number, plan_id):
    """
    Send welcome email when user converts from trial to paid subscription
    """
    try:
        user = User.query.get(user_id)
        plan = SubscriptionPlan.query.get(plan_id)
        
        if not user or not plan:
            return {'success': False, 'error': 'User or plan not found'}
        
        email_data = {
            'first_name': first_name,
            'phone_number': phone_number,
            'plan_name': plan.name,
            'plan_price': f"${plan.monthly_price:.2f}",
            'billing_cycle': 'monthly',
            'dashboard_url': f"{current_app.config.get('FRONTEND_URL')}/dashboard",
            'billing_url': f"{current_app.config.get('FRONTEND_URL')}/dashboard/billing",
            'support_email': current_app.config.get('SUPPORT_EMAIL'),
            'company_name': 'AssisText',
            'features_list': _get_plan_features(plan_id),
            'next_billing_date': (datetime.utcnow() + timedelta(days=30)).strftime('%B %d, %Y')
        }
        
        _send_email_with_template(
            to_email=email,
            subject=f"Welcome to AssisText {plan.name} Plan!",
            template='emails/subscription_welcome.html',
            email_data=email_data
        )
        
        logger.info(f"✅ Subscription welcome email sent to user {user_id}")
        
        return {
            'success': True,
            'user_id': user_id,
            'plan_id': plan_id,
            'email_type': 'subscription_welcome',
            'sent_at': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to send subscription welcome email to user {user_id}: {e}")
        
        if self.request.retries < self.max_retries:
            retry_delay = 2 ** self.request.retries * 60
            raise self.retry(countdown=retry_delay, exc=e)
        
        return {'success': False, 'error': str(e)}

@celery.task(bind=True, max_retries=3)
def send_payment_failed_email(self, user_id, email, first_name, amount, retry_date):
    """
    Send notification when subscription payment fails
    """
    try:
        email_data = {
            'first_name': first_name,
            'amount': f"${amount:.2f}",
            'retry_date': retry_date,
            'update_payment_url': f"{current_app.config.get('FRONTEND_URL')}/dashboard/billing",
            'support_email': current_app.config.get('SUPPORT_EMAIL'),
            'company_name': 'AssisText'
        }
        
        _send_email_with_template(
            to_email=email,
            subject="Payment Failed - Update Your Payment Method",
            template='emails/payment_failed.html',
            email_data=email_data
        )
        
        logger.info(f"✅ Payment failed email sent to user {user_id}")
        
        return {
            'success': True,
            'user_id': user_id,
            'email_type': 'payment_failed',
            'sent_at': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to send payment failed email to user {user_id}: {e}")
        
        if self.request.retries < self.max_retries:
            retry_delay = 2 ** self.request.retries * 60
            raise self.retry(countdown=retry_delay, exc=e)
        
        return {'success': False, 'error': str(e)}

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def _send_email_with_template(to_email, subject, template, email_data):
    """
    Send email using Flask-Mail with HTML template
    """
    try:
        with current_app.app_context():
            # Create message
            msg = Message(
                subject=subject,
                recipients=[to_email],
                sender=current_app.config.get('MAIL_DEFAULT_SENDER', 'noreply@assistext.com')
            )
            
            # Render HTML template
            msg.html = render_template(template, **email_data)
            
            # Optional: Add plain text version
            try:
                text_template = template.replace('.html', '.txt')
                msg.body = render_template(text_template, **email_data)
            except:
                # If no text template exists, create simple text version
                msg.body = f"Hello {email_data.get('first_name', 'there')},\n\n" + \
                          f"Please view this email in HTML format.\n\n" + \
                          f"Best regards,\nThe AssisText Team"
            
            # Send email
            Mail.send(msg)
            
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}")
        raise

def _get_trial_usage_stats(user_id):
    """
    Get usage statistics for trial user
    """
    try:
        user = User.query.get(user_id)
        if not user:
            return {}
        
        # Calculate trial usage (you'll need to implement based on your models)
        from app.models.messaging import Message
        from app.models.client import Client
        
        message_count = Message.query.filter_by(user_id=user_id).count()
        client_count = Client.query.filter_by(user_id=user_id).count()
        
        trial_start = user.trial_start_date or user.created_at
        days_used = (datetime.utcnow() - trial_start).days
        
        return {
            'messages_processed': message_count,
            'clients_managed': client_count,
            'days_used': days_used,
            'phone_number': user.signalwire_phone_number
        }
        
    except Exception as e:
        logger.error(f"Failed to get trial stats for user {user_id}: {e}")
        return {}

def _get_plan_features(plan_id):
    """
    Get feature list for subscription plan
    """
    # This should match your actual plan features
    features_map = {
        1: [  # Basic plan
            "Dedicated phone number",
            "AI-powered SMS responses", 
            "Up to 1,000 messages/month",
            "Basic customer management",
            "Email support"
        ],
        2: [  # Pro plan
            "Dedicated phone number",
            "Advanced AI responses",
            "Up to 5,000 messages/month", 
            "Advanced customer management",
            "Priority support",
            "Custom AI personality"
        ],
        3: [  # Enterprise plan
            "Multiple phone numbers",
            "Enterprise AI features",
            "Unlimited messages",
            "Full customer management suite",
            "24/7 phone support",
            "Custom integrations"
        ]
    }
    
    return features_map.get(plan_id, features_map[1])

# =============================================================================
# SCHEDULED EMAIL TASKS
# =============================================================================

@celery.task
def send_daily_trial_reminders():
    """
    Daily task to send trial setup reminders to users who haven't added payment
    Run this as a scheduled Celery Beat task
    """
    try:
        # Find users who registered 24+ hours ago but haven't added payment
        cutoff_time = datetime.utcnow() - timedelta(hours=24)
        
        users_needing_reminder = User.query.filter(
            User.trial_status == 'pending_payment',
            User.created_at <= cutoff_time
        ).all()
        
        results = []
        for user in users_needing_reminder:
            result = send_trial_setup_reminder.delay(
                user_id=user.id,
                email=user.email,
                first_name=user.first_name
            )
            results.append({
                'user_id': user.id,
                'task_id': result.id
            })
        
        logger.info(f"✅ Scheduled {len(results)} trial setup reminders")
        
        return {
            'success': True,
            'reminders_sent': len(results),
            'task_ids': [r['task_id'] for r in results]
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to send daily trial reminders: {e}")
        return {'success': False, 'error': str(e)}

@celery.task
def cleanup_old_email_logs():
    """
    Clean up old email logs and notifications
    Run weekly to maintain database performance
    """
    try:
        # Remove email logs older than 90 days
        cutoff_date = datetime.utcnow() - timedelta(days=90)
        
        # You'll need to implement based on your email logging model
        # EmailLog.query.filter(EmailLog.created_at < cutoff_date).delete()
        # db.session.commit()
        
        logger.info("✅ Cleaned up old email logs")
        return {'success': True, 'cleaned_up': True}
        
    except Exception as e:
        logger.error(f"❌ Failed to cleanup email logs: {e}")
        return {'success': False, 'error': str(e)}

# =============================================================================
# CELERY BEAT SCHEDULE (Add to your celery config)
# =============================================================================

EMAIL_CELERY_BEAT_SCHEDULE = {
    'send-daily-trial-reminders': {
        'task': 'app.tasks.email_tasks.send_daily_trial_reminders',
        'schedule': 3600.0,  # Run every hour
        'options': {'queue': 'email_notifications'}
    },
    'cleanup-email-logs': {
        'task': 'app.tasks.email_tasks.cleanup_old_email_logs',
        'schedule': 604800.0,  # Run weekly
        'options': {'queue': 'maintenance'}
    }
}