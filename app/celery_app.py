#!/usr/bin/env python3
"""
Celery Worker Entry Point for AssisText
Properly configured with consolidated services and task discovery
"""

import os
import sys
import logging
from dotenv import load_dotenv

# Configure logging early
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Add project root to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

logger.info(f"🚀 Starting Celery configuration from: {project_root}")

# =============================================================================
# CELERY CONFIGURATION
# =============================================================================

from celery import Celery

# Create Celery instance
celery_app = Celery('assistext')

# Basic Celery configuration
celery_config = {
    # Broker and Backend
    'broker_url': os.getenv('CELERY_BROKER_URL', 'redis://:Assistext2025Secure@localhost:6379/0'),
    'result_backend': os.getenv('CELERY_RESULT_BACKEND', 'redis://:Assistext2025Secure@localhost:6379/0'),
    
    # Serialization
    'task_serializer': 'json',
    'accept_content': ['json'],
    'result_serializer': 'json',
    
    # Timezone
    'timezone': 'UTC',
    'enable_utc': True,
    
    # Task discovery - Include all task modules
    'include': [
        'app.tasks.email_tasks',
        'app.tasks.trial_tasks', 
        'app.tasks.background_tasks'  # Include if available
    ],
    
    # Worker configuration
    'worker_prefetch_multiplier': 1,  # Ensures fair task distribution
    'task_acks_late': True,          # Acknowledge tasks only after completion
    'worker_disable_rate_limits': False,
    
    # Task routing - Route tasks to appropriate queues
    'task_routes': {
        'app.tasks.email_tasks.*': {'queue': 'email_notifications'},
        'app.tasks.trial_tasks.*': {'queue': 'trial_management'},
        'app.tasks.background_tasks.*': {'queue': 'background_processing'},
    },
    
    # Default queue configuration
    'task_default_queue': 'default',
    'task_default_exchange': 'default',
    'task_default_exchange_type': 'direct',
    'task_default_routing_key': 'default',
    
    # Result backend settings
    'result_expires': 3600,  # Results expire after 1 hour
    'result_persistent': True,
    
    # Task execution settings
    'task_time_limit': 300,      # 5 minute hard time limit
    'task_soft_time_limit': 240,  # 4 minute soft time limit
    'task_max_retries': 3,
    'task_default_retry_delay': 60,  # 1 minute retry delay
    
    # Monitoring and logging
    'worker_send_task_events': True,
    'task_send_sent_event': True,
    'worker_log_format': '[%(asctime)s: %(levelname)s/%(processName)s] %(message)s',
    'worker_task_log_format': '[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s',
}

# Apply configuration to Celery app
celery_app.conf.update(celery_config)

logger.info("✅ Celery basic configuration applied")

# =============================================================================
# TASK DISCOVERY AND REGISTRATION
# =============================================================================

def register_tasks_and_schedules():
    """
    Register all tasks and configure beat schedules
    This runs during Celery startup
    """
    logger.info("🔄 Starting task registration...")
    
    # Import tasks package to register all tasks
    try:
        from app.tasks import (
            get_all_registered_tasks,
            get_beat_schedule,
            get_task_summary,
            run_task_diagnostics
        )
        
        # Get task summary
        summary = get_task_summary()
        logger.info(f"📋 Task summary: {summary['available_tasks']}/{summary['total_tasks']} tasks available")
        
        # Get all registered tasks
        registered_tasks = get_all_registered_tasks()
        logger.info(f"✅ Registered {len(registered_tasks)} tasks: {', '.join(registered_tasks)}")
        
        # Configure beat schedule
        beat_schedule = get_beat_schedule()
        if beat_schedule:
            celery_app.conf.beat_schedule = beat_schedule
            logger.info(f"⏰ Configured {len(beat_schedule)} scheduled tasks")
            for schedule_name in beat_schedule.keys():
                logger.info(f"  - {schedule_name}")
        else:
            logger.warning("⚠️ No beat schedule configured")
        
        # Run diagnostics if in debug mode
        if os.getenv('DEBUG', 'False').lower() == 'true':
            diagnostics = run_task_diagnostics()
            logger.info(f"🔍 Task diagnostics: {diagnostics['package_status']}")
            
            if diagnostics.get('recommendations'):
                for rec in diagnostics['recommendations']:
                    logger.warning(f"💡 Recommendation: {rec}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to register tasks: {e}")
        return False

# =============================================================================
# SERVICE INTEGRATION
# =============================================================================

def initialize_services():
    """
    Initialize all services for Celery workers
    This ensures services are available when tasks execute
    """
    logger.info("🔧 Initializing services for Celery workers...")
    
    try:
        from app.services import initialize_all_services, ServiceManager
        
        # Initialize all services
        init_results = initialize_all_services()
        
        # Log initialization results
        for service, status in init_results.items():
            if status == 'initialized':
                logger.info(f"✅ {service} service: {status}")
            else:
                logger.error(f"❌ {service} service: {status}")
        
        # Check overall service health
        health_status = ServiceManager.check_services_health()
        logger.info(f"🏥 Overall service health: {health_status['overall']}")
        
        return init_results
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize services: {e}")
        return {}

# =============================================================================
# CELERY SIGNALS - Hooks for worker lifecycle events
# =============================================================================

from celery.signals import (
    worker_init, 
    worker_ready, 
    worker_shutdown,
    task_prerun,
    task_postrun,
    task_failure
)

@worker_init.connect
def worker_init_handler(sender=None, **kwargs):
    """Called when worker process is initialized"""
    logger.info("👷 Celery worker initializing...")

@worker_ready.connect
def worker_ready_handler(sender=None, **kwargs):
    """Called when worker is ready to receive tasks"""
    logger.info("🟢 Celery worker ready to receive tasks")
    
    # Initialize services when worker is ready
    service_results = initialize_services()
    
    # Register tasks and schedules
    task_registration_success = register_tasks_and_schedules()
    
    if task_registration_success:
        logger.info("✅ Celery worker fully initialized and ready")
    else:
        logger.error("❌ Celery worker initialization completed with errors")

@worker_shutdown.connect
def worker_shutdown_handler(sender=None, **kwargs):
    """Called when worker is shutting down"""
    logger.info("🔴 Celery worker shutting down...")

@task_prerun.connect
def task_prerun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, **kwds):
    """Called before task execution"""
    logger.info(f"▶️ Starting task: {task.name} (ID: {task_id})")

@task_postrun.connect
def task_postrun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, retval=None, state=None, **kwds):
    """Called after task execution"""
    if state == 'SUCCESS':
        logger.info(f"✅ Completed task: {task.name} (ID: {task_id})")
    else:
        logger.warning(f"⚠️ Task finished with state {state}: {task.name} (ID: {task_id})")

@task_failure.connect
def task_failure_handler(sender=None, task_id=None, exception=None, traceback=None, einfo=None, **kwds):
    """Called when task fails"""
    logger.error(f"❌ Task failed: {sender.name} (ID: {task_id}) - {exception}")

# =============================================================================
# HEALTH CHECK ENDPOINTS
# =============================================================================

@celery_app.task(name='celery.health_check')
def health_check():
    """
    Health check task for monitoring
    Tests basic task execution and service availability
    """
    try:
        from app.services import ServiceManager
        
        # Check service health
        health_status = ServiceManager.check_services_health()
        
        # Check task system
        from app.tasks import get_task_summary
        task_summary = get_task_summary()
        
        return {
            'status': 'healthy',
            'timestamp': None,  # Will be set by calling code
            'services': health_status,
            'tasks': task_summary,
            'worker_active': True
        }
    except Exception as e:
        return {
            'status': 'unhealthy',
            'error': str(e),
            'worker_active': True
        }

@celery_app.task(name='celery.ping')
def ping():
    """Simple ping task for basic connectivity testing"""
    return {'status': 'pong', 'worker_active': True}

# =============================================================================
# CELERY APP FACTORY (Alternative initialization method)
# =============================================================================

def create_celery_app(app=None):
    """
    Factory function to create Celery app with Flask application context
    Use this when integrating with Flask application
    """
    if app is not None:
        # Update configuration from Flask app config
        celery_app.conf.update(
            broker_url=app.config.get('CELERY_BROKER_URL', celery_config['broker_url']),
            result_backend=app.config.get('CELERY_RESULT_BACKEND', celery_config['result_backend']),
        )
        
        # Setup task context to work with Flask app context
        class ContextTask(celery_app.Task):
            """Make celery tasks work with Flask app context."""
            def __call__(self, *args, **kwargs):
                with app.app_context():
                    return self.run(*args, **kwargs)
        
        celery_app.Task = ContextTask
        logger.info("🔗 Celery app configured with Flask context")
    
    return celery_app

# =============================================================================
# STARTUP EXECUTION
# =============================================================================

if __name__ == '__main__':
    """
    Direct execution - starts Celery worker
    Use this for development or when running celery directly
    """
    logger.info("🚀 Starting Celery worker directly...")
    
    # Register tasks and services immediately
    service_results = initialize_services()
    task_success = register_tasks_and_schedules()
    
    if task_success:
        logger.info("✅ Starting Celery worker with all tasks registered")
        # Start the worker
        celery_app.start([
            'worker',
            '--loglevel=info',
            '--concurrency=4',
            '--queues=default,email_notifications,trial_management,background_processing'
        ])
    else:
        logger.error("❌ Failed to register tasks - starting basic worker")
        celery_app.start(['worker', '--loglevel=info'])

else:
    """
    Module import - Celery app is available for external use
    This is used when starting with: celery -A celery_app worker
    """
    logger.info("📦 Celery app module loaded and ready for external commands")