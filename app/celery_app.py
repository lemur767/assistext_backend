# celery_app.py - Updated Celery configuration for AssisText
import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add app to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import and configure Celery
from app.extensions import make_celery

# Create Celery app
celery_app = make_celery()

# Import all task modules so Celery can discover them
try:
    # Import existing tasks
    from app.tasks import trial_tasks
    
    # Import new email tasks
    from app.tasks import email_tasks
    
    print("✅ Task modules imported successfully")
except ImportError as e:
    print(f"⚠️ Warning: Could not import task modules: {e}")

# =============================================================================
# CELERY BEAT SCHEDULE CONFIGURATION
# =============================================================================

# Import beat schedules from task modules
try:
    from app.tasks.email_tasks import EMAIL_CELERY_BEAT_SCHEDULE
except ImportError as e:
    print(f"⚠️ Warning: Could not import EMAIL_CELERY_BEAT_SCHEDULE: {e}")
    EMAIL_CELERY_BEAT_SCHEDULE = {}

# Your existing beat schedule (if any)
EXISTING_BEAT_SCHEDULE = {
    # Add any existing scheduled tasks here
    # 'existing-task': {
    #     'task': 'app.tasks.existing_task',
    #     'schedule': 3600.0,
    # }
}

# Combine all beat schedules
COMBINED_BEAT_SCHEDULE = {
    **EXISTING_BEAT_SCHEDULE,
    **EMAIL_CELERY_BEAT_SCHEDULE,
}

# Configure Celery Beat
celery_app.conf.beat_schedule = COMBINED_BEAT_SCHEDULE
celery_app.conf.timezone = 'UTC'

# =============================================================================
# CELERY TASK ROUTING CONFIGURATION
# =============================================================================

# Configure task routing for different queues
celery_app.conf.task_routes = {
    # Email tasks
    'app.tasks.email_tasks.send_welcome_email': {'queue': 'email_notifications'},
    'app.tasks.email_tasks.send_trial_warning_email': {'queue': 'email_notifications'},
    'app.tasks.email_tasks.send_trial_expired_email': {'queue': 'email_notifications'},
    'app.tasks.email_tasks.send_subscription_welcome_email': {'queue': 'email_notifications'},
    'app.tasks.email_tasks.send_payment_failed_email': {'queue': 'email_notifications'},
    'app.tasks.email_tasks.send_trial_setup_reminder': {'queue': 'email_notifications'},
    'app.tasks.email_tasks.send_daily_trial_reminders': {'queue': 'email_notifications'},
    
    # Trial management tasks
    'app.tasks.trial_tasks.schedule_trial_expiry': {'queue': 'trial_management'},
    'app.tasks.trial_tasks.send_trial_warning': {'queue': 'trial_management'},
    'app.tasks.trial_tasks.expire_trial': {'queue': 'trial_management'},
    'app.tasks.trial_tasks.reactivate_user': {'queue': 'trial_management'},
    'app.tasks.trial_tasks.check_trial_status_daily': {'queue': 'trial_management'},
    
    # Default queue for other tasks
    # Any other tasks will go to 'default' queue
}

# =============================================================================
# ADDITIONAL CELERY CONFIGURATION
# =============================================================================

# Task execution settings
celery_app.conf.task_serializer = 'json'
celery_app.conf.accept_content = ['json']
celery_app.conf.result_serializer = 'json'
celery_app.conf.task_always_eager = False  # Set to True only for testing

# Task retry settings
celery_app.conf.task_acks_late = True
celery_app.conf.worker_prefetch_multiplier = 1

# Task time limits
celery_app.conf.task_soft_time_limit = 300  # 5 minutes
celery_app.conf.task_time_limit = 600  # 10 minutes

# Email task specific settings
celery_app.conf.task_routes.update({
    # Prioritize certain email tasks
    'app.tasks.email_tasks.send_trial_expired_email': {
        'queue': 'email_notifications',
        'priority': 9  # High priority
    },
    'app.tasks.email_tasks.send_payment_failed_email': {
        'queue': 'email_notifications', 
        'priority': 8  # High priority
    },
})

# Logging configuration
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

if __name__ == '__main__':
    print("🚀 Starting Celery with email task support...")
    print(f"📧 Email tasks beat schedule: {len(EMAIL_CELERY_BEAT_SCHEDULE)} scheduled tasks")
    print(f"🔄 Total beat schedule: {len(COMBINED_BEAT_SCHEDULE)} scheduled tasks")
    print(f"📝 Task routes configured: {len(celery_app.conf.task_routes)} routes")
    celery_app.start()