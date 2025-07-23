"""Tasks Package for AssisText"""

try:
    from .email_tasks import (
        send_welcome_email,
        send_trial_warning_email,
        send_trial_expired_email,
        EMAIL_CELERY_BEAT_SCHEDULE
    )
    __all__ = [
        'send_welcome_email',
        'send_trial_warning_email', 
        'send_trial_expired_email',
        'EMAIL_CELERY_BEAT_SCHEDULE'
    ]
except ImportError as e:
    print(f"Could not import email tasks: {e}")
    __all__ = []
