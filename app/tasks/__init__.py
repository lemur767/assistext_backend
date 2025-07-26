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

print(f"📝 Tasks package initialized with {len(__all__)} exported functions")# app/tasks/__init__.py
"""
Tasks package for AssisText
Fixed to handle missing dependencies gracefully
"""

import logging

logger = logging.getLogger(__name__)

# Available task functions
available_functions = []

# Try to import email tasks
try:
    from .email_tasks import (
        send_welcome_email,
        send_trial_warning_email,
        send_payment_failed_email
    )
    available_functions.extend([
        'send_welcome_email',
        'send_trial_warning_email', 
        'send_payment_failed_email'
    ])
    logger.info("✅ Email tasks imported successfully")
except ImportError as e:
    logger.warning(f"⚠️ Email tasks not available: {e}")

# Try to import trial tasks
try:
    from .trial_tasks import (
        check_trial_expiring_users,
        suspend_expired_trials,
        activate_trial_for_user,
        get_trial_status
    )
    available_functions.extend([
        'check_trial_expiring_users',
        'suspend_expired_trials',
        'activate_trial_for_user',
        'get_trial_status'
    ])
    logger.info("✅ Trial tasks imported successfully")
except ImportError as e:
    logger.warning(f"⚠️ Trial tasks not available: {e}")

# Try to import billing tasks
try:
    from .billing_tasks import (
        process_invoice,
        send_payment_reminder,
        update_subscription_status
    )
    available_functions.extend([
        'process_invoice',
        'send_payment_reminder',
        'update_subscription_status'
    ])
    logger.info("✅ Billing tasks imported successfully")
except ImportError as e:
    logger.warning(f"⚠️ Billing tasks not available: {e}")

# Celery configuration (if available)
try:
    from celery import Celery
    
    def make_celery(app):
        """Create Celery instance"""
        celery = Celery(
            app.import_name,
            backend=app.config.get('CELERY_RESULT_BACKEND'),
            broker=app.config.get('CELERY_BROKER_URL')
        )
        celery.conf.update(app.config)
        
        class ContextTask(celery.Task):
            """Make celery tasks work with Flask app context."""
            def __call__(self, *args, **kwargs):
                with app.app_context():
                    return self.run(*args, **kwargs)
        
        celery.Task = ContextTask
        return celery
    
    CELERY_AVAILABLE = True
    logger.info("✅ Celery available for task scheduling")
    
except ImportError:
    CELERY_AVAILABLE = False
    logger.warning("⚠️ Celery not available, tasks will run synchronously")
    
    def make_celery(app):
        """Dummy celery maker when Celery not available"""
        return None

# Task registry for manual execution
task_registry = {}

def register_task(name, func):
    """Register a task function"""
    task_registry[name] = func
    available_functions.append(name)

def get_task(name):
    """Get a registered task function"""
    return task_registry.get(name)

def list_tasks():
    """List all available tasks"""
    return available_functions.copy()

def execute_task(task_name, *args, **kwargs):
    """Execute a task by name"""
    task_func = get_task(task_name)
    if task_func:
        try:
            return task_func(*args, **kwargs)
        except Exception as e:
            logger.error(f"❌ Task {task_name} failed: {e}")
            return {'success': False, 'error': str(e)}
    else:
        logger.error(f"❌ Task {task_name} not found")
        return {'success': False, 'error': f'Task {task_name} not found'}

# Health check for tasks
def tasks_health_check():
    """Check health of task system"""
    return {
        'celery_available': CELERY_AVAILABLE,
        'tasks_available': len(available_functions),
        'task_list': available_functions,
        'status': 'healthy' if available_functions else 'degraded'
    }

logger.info(f"📝 Tasks package initialized with {len(available_functions)} exported functions")

# Export main functions
__all__ = [
    'make_celery',
    'register_task',
    'get_task',
    'list_tasks',
    'execute_task',
    'tasks_health_check',
    'available_functions',
    'CELERY_AVAILABLE'
]