"""
Tasks Package for AssisText - Celery Task Definitions
Exports all Celery tasks for easy importing and registration

This package contains:
- Email tasks: Welcome emails, trial reminders, notifications
- Trial tasks: Trial management, expiry handling, status checks
- Background tasks: Cleanup, maintenance, scheduled operations
"""

import logging
from typing import Dict, List, Any

# =============================================================================
# TASK IMPORTS - Import all task modules
# =============================================================================

# Track successfully imported task modules
_imported_modules = []
_all_tasks = []
_beat_schedules = {}

# Email Tasks Import
try:
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
    
    # Add to exports
    _all_tasks.extend([
        'send_welcome_email',
        'send_trial_setup_reminder', 
        'send_trial_warning_email',
        'send_trial_expired_email',
        'send_subscription_welcome_email',
        'send_payment_failed_email',
        'send_daily_trial_reminders',
        'cleanup_old_email_logs',
    ])
    
    # Merge beat schedule
    _beat_schedules.update(EMAIL_CELERY_BEAT_SCHEDULE)
    _imported_modules.append('email_tasks')
    
    logging.info("✅ Email tasks imported successfully")
    
except ImportError as e:
    logging.error(f"❌ Could not import email tasks: {e}")
    send_welcome_email = None
    send_trial_setup_reminder = None
    send_trial_warning_email = None
    send_trial_expired_email = None
    send_subscription_welcome_email = None
    send_payment_failed_email = None
    send_daily_trial_reminders = None
    cleanup_old_email_logs = None
    EMAIL_CELERY_BEAT_SCHEDULE = {}

# Trial Tasks Import
try:
    from .trial_tasks import (
        schedule_trial_expiry,
        send_trial_warning,
        expire_trial,
        reactivate_user,
        check_trial_status_daily,
        TRIAL_CELERY_BEAT_SCHEDULE
    )
    
    # Add to exports
    _all_tasks.extend([
        'schedule_trial_expiry',
        'send_trial_warning', 
        'expire_trial',
        'reactivate_user',
        'check_trial_status_daily'
    ])
    
    # Merge beat schedule
    _beat_schedules.update(TRIAL_CELERY_BEAT_SCHEDULE)
    _imported_modules.append('trial_tasks')
    
    logging.info("✅ Trial tasks imported successfully")
    
except ImportError as e:
    logging.error(f"❌ Could not import trial tasks: {e}")
    schedule_trial_expiry = None
    send_trial_warning = None
    expire_trial = None
    reactivate_user = None
    check_trial_status_daily = None
    TRIAL_CELERY_BEAT_SCHEDULE = {}

# Background Tasks Import (optional)
try:
    from .background_tasks import (
        cleanup_old_messages,
        update_usage_statistics,
        generate_daily_reports,
        backup_database,
        BACKGROUND_CELERY_BEAT_SCHEDULE
    )
    
    # Add to exports
    _all_tasks.extend([
        'cleanup_old_messages',
        'update_usage_statistics',
        'generate_daily_reports',
        'backup_database'
    ])
    
    # Merge beat schedule
    _beat_schedules.update(BACKGROUND_CELERY_BEAT_SCHEDULE)
    _imported_modules.append('background_tasks')
    
    logging.info("✅ Background tasks imported successfully")
    
except ImportError as e:
    logging.warning(f"⚠️ Background tasks not available: {e}")
    cleanup_old_messages = None
    update_usage_statistics = None
    generate_daily_reports = None
    backup_database = None
    BACKGROUND_CELERY_BEAT_SCHEDULE = {}

# =============================================================================
# CONSOLIDATED BEAT SCHEDULE
# =============================================================================

# Combine all beat schedules into one master schedule
CONSOLIDATED_BEAT_SCHEDULE = {}
CONSOLIDATED_BEAT_SCHEDULE.update(_beat_schedules)

# =============================================================================
# TASK REGISTRY AND MANAGEMENT
# =============================================================================

def get_all_registered_tasks() -> List[str]:
    """Get list of all successfully imported task names"""
    return [task for task in _all_tasks if task is not None]

def get_imported_modules() -> List[str]:
    """Get list of successfully imported task modules"""
    return _imported_modules.copy()

def get_beat_schedule() -> Dict[str, Any]:
    """Get consolidated Celery beat schedule"""
    return CONSOLIDATED_BEAT_SCHEDULE.copy()

def check_task_availability() -> Dict[str, bool]:
    """Check which tasks are available for use"""
    task_status = {}
    
    # Check email tasks
    email_tasks = [
        'send_welcome_email',
        'send_trial_setup_reminder',
        'send_trial_warning_email',
        'send_trial_expired_email',
        'send_subscription_welcome_email',
        'send_payment_failed_email',
        'send_daily_trial_reminders',
        'cleanup_old_email_logs'
    ]
    
    for task in email_tasks:
        task_status[task] = globals().get(task) is not None
    
    # Check trial tasks
    trial_tasks = [
        'schedule_trial_expiry',
        'send_trial_warning',
        'expire_trial',
        'reactivate_user',
        'check_trial_status_daily'
    ]
    
    for task in trial_tasks:
        task_status[task] = globals().get(task) is not None
    
    # Check background tasks
    background_tasks = [
        'cleanup_old_messages',
        'update_usage_statistics',
        'generate_daily_reports',
        'backup_database'
    ]
    
    for task in background_tasks:
        task_status[task] = globals().get(task) is not None
    
    return task_status

def get_task_summary() -> Dict[str, Any]:
    """Get comprehensive summary of task package status"""
    task_availability = check_task_availability()
    
    available_count = sum(1 for available in task_availability.values() if available)
    total_count = len(task_availability)
    
    return {
        'imported_modules': _imported_modules,
        'available_tasks': available_count,
        'total_tasks': total_count,
        'task_availability': task_availability,
        'beat_schedule_entries': len(CONSOLIDATED_BEAT_SCHEDULE),
        'health_status': 'healthy' if available_count > 0 else 'no_tasks_available'
    }

# =============================================================================
# TASK EXECUTION HELPERS
# =============================================================================

def queue_email_task(task_name: str, *args, **kwargs) -> Any:
    """
    Helper to safely queue email tasks with error handling
    """
    task_func = globals().get(task_name)
    if task_func is None:
        logging.error(f"❌ Email task '{task_name}' not available")
        return None
    
    try:
        # Queue the task for execution
        result = task_func.delay(*args, **kwargs)
        logging.info(f"✅ Queued email task '{task_name}' with ID: {result.id}")
        return result
    except Exception as e:
        logging.error(f"❌ Failed to queue email task '{task_name}': {e}")
        return None

def queue_trial_task(task_name: str, *args, **kwargs) -> Any:
    """
    Helper to safely queue trial management tasks with error handling
    """
    task_func = globals().get(task_name)
    if task_func is None:
        logging.error(f"❌ Trial task '{task_name}' not available")
        return None
    
    try:
        # Queue the task for execution
        result = task_func.delay(*args, **kwargs)
        logging.info(f"✅ Queued trial task '{task_name}' with ID: {result.id}")
        return result
    except Exception as e:
        logging.error(f"❌ Failed to queue trial task '{task_name}': {e}")
        return None

# =============================================================================
# INITIALIZATION DIAGNOSTICS
# =============================================================================

def run_task_diagnostics() -> Dict[str, Any]:
    """
    Run comprehensive diagnostics on task package
    Useful for debugging and system health checks
    """
    diagnostics = {
        'timestamp': None,
        'package_status': 'unknown',
        'modules': {},
        'tasks': {},
        'beat_schedule': {},
        'recommendations': []
    }
    
    try:
        from datetime import datetime
        diagnostics['timestamp'] = datetime.utcnow().isoformat()
        
        # Check module imports
        for module in ['email_tasks', 'trial_tasks', 'background_tasks']:
            if module in _imported_modules:
                diagnostics['modules'][module] = 'imported'
            else:
                diagnostics['modules'][module] = 'not_imported'
                diagnostics['recommendations'].append(f"Consider creating {module}.py if needed")
        
        # Check task availability
        diagnostics['tasks'] = check_task_availability()
        
        # Check beat schedule
        diagnostics['beat_schedule'] = {
            'total_entries': len(CONSOLIDATED_BEAT_SCHEDULE),
            'entries': list(CONSOLIDATED_BEAT_SCHEDULE.keys())
        }
        
        # Determine overall status
        available_tasks = sum(1 for available in diagnostics['tasks'].values() if available)
        if available_tasks == 0:
            diagnostics['package_status'] = 'no_tasks_available'
            diagnostics['recommendations'].append("No tasks are available - check task module imports")
        elif available_tasks < len(diagnostics['tasks']) // 2:
            diagnostics['package_status'] = 'partially_available'
            diagnostics['recommendations'].append("Some tasks are missing - check for import errors")
        else:
            diagnostics['package_status'] = 'healthy'
        
    except Exception as e:
        diagnostics['package_status'] = 'error'
        diagnostics['error'] = str(e)
        diagnostics['recommendations'].append("Check task package imports for errors")
    
    return diagnostics

# =============================================================================
# EXPORTS
# =============================================================================

# Export all available tasks
__all__ = _all_tasks + [
    # Task management functions
    'get_all_registered_tasks',
    'get_imported_modules',
    'get_beat_schedule',
    'check_task_availability',
    'get_task_summary',
    
    # Task execution helpers
    'queue_email_task',
    'queue_trial_task',
    
    # Diagnostics
    'run_task_diagnostics',
    
    # Beat schedule
    'CONSOLIDATED_BEAT_SCHEDULE',
    'EMAIL_CELERY_BEAT_SCHEDULE',
    'TRIAL_CELERY_BEAT_SCHEDULE',
    'BACKGROUND_CELERY_BEAT_SCHEDULE',
]

# =============================================================================
# PACKAGE INITIALIZATION LOGGING
# =============================================================================

# Log initialization summary
summary = get_task_summary()
logging.info(f"📋 Tasks package initialized: {summary['available_tasks']}/{summary['total_tasks']} tasks available")

if summary['available_tasks'] == 0:
    logging.error("❌ No tasks are available! Check task module imports.")
elif summary['available_tasks'] < summary['total_tasks']:
    logging.warning(f"⚠️ Only {summary['available_tasks']}/{summary['total_tasks']} tasks imported successfully")
    missing_tasks = [task for task, available in summary['task_availability'].items() if not available]
    logging.warning(f"Missing tasks: {', '.join(missing_tasks)}")
else:
    logging.info("✅ All tasks imported successfully")

if summary['beat_schedule_entries'] > 0:
    logging.info(f"⏰ Configured {summary['beat_schedule_entries']} scheduled tasks")
else:
    logging.warning("⚠️ No scheduled tasks configured")