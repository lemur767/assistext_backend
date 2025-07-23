# app/tasks/__init__.py
try:
    # Import email tasks
    from .email_tasks import (
        send_welcome_email,
        send_trial_setup_reminder,
        send_trial_warning_email,
        send_trial_expired_email,
        send_subscription_welcome_email,
        send_payment_failed_email,
        send_daily_trial_reminders,
        cleanup_old_email_logs,
        EMAIL_CELERY_BEAT_SCHEDULE
    )
    
    print("✅ Email tasks imported successfully")
    
    # Export email tasks
    __all__ = [
        'send_welcome_email',
        'send_trial_setup_reminder', 
        'send_trial_warning_email',
        'send_trial_expired_email',
        'send_subscription_welcome_email',
        'send_payment_failed_email',
        'send_daily_trial_reminders',
        'cleanup_old_email_logs',
        'EMAIL_CELERY_BEAT_SCHEDULE'
    ]
    
except ImportError as e:
    print(f"⚠️ Could not import email tasks: {e}")
    __all__ = []

# Import trial tasks if they exist
try:
    from .trial_tasks import (
        schedule_trial_expiry,
        send_trial_warning,
        expire_trial,
        reactivate_user,
        check_trial_status_daily
    )
    
    print("✅ Trial tasks imported successfully")
    
    # Add trial tasks to exports
    __all__.extend([
        'schedule_trial_expiry',
        'send_trial_warning', 
        'expire_trial',
        'reactivate_user',
        'check_trial_status_daily'
    ])
    
except ImportError as e:
    print(f"⚠️ Could not import trial tasks: {e}")

# Make sure __all__ has at least something
if not __all__:
    __all__ = []

print(f"📝 Tasks package initialized with {len(__all__)} exported functions")