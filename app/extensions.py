"""
Updated Flask Extensions with Celery Export
app/extensions.py - Complete extension initialization for AssisText
"""
import os
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from flask_socketio import SocketIO
from flask_mail import Mail
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from celery import Celery
import redis
import logging

# Initialize extensions without app - EXPORTED FOR IMPORTS
db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()
socketio = SocketIO()
mail = Mail()

# Initialize rate limiter - EXPORTED FOR IMPORTS  
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["1000 per day", "100 per hour"]
)

# Initialize Redis connection - EXPORTED FOR IMPORTS
redis_client = None

# Initialize Celery - EXPORTED FOR IMPORTS
celery = None

def make_celery(app=None):
    """
    Create and configure Celery instance
    
    Args:
        app: Flask application instance
    
    Returns:
        Configured Celery instance
    """
    global celery
    
    broker_url = os.getenv('CELERY_BROKER_URL', 'redis://AssisText2025!Redis:@172.234.219.10:6379/0')
    result_backend = os.getenv('CELERY_RESULT_BACKEND', 'redis://AssisText2025!Redis:@172.234.219.10:6379/0')
    
    # Create or update global celery instance
    if celery is None:
        celery = Celery(
            'assistext',
            broker=broker_url,
            backend=result_backend,
            include=['app.tasks']  # Include tasks module
        )
    
    # Configure Celery
    celery.conf.update(
        # Task settings
        task_serializer='json',
        accept_content=['json'],
        result_serializer='json',
        timezone='America/Toronto',
        enable_utc=True,
        
        # Worker settings
        worker_prefetch_multiplier=1,
        task_acks_late=True,
        worker_max_tasks_per_child=1000,
        
        # Result settings
        result_expires=3600,  # 1 hour
        
        # Routing
        task_routes={
            'app.tasks.process_incoming_sms': {'queue': 'sms_processing'},
            'app.tasks.generate_ai_response': {'queue': 'ai_processing'},
            'app.tasks.send_sms_message': {'queue': 'sms_sending'},
            'app.tasks.update_message_status': {'queue': 'status_updates'},
        },
        
        # Queue settings
        task_default_queue='default',
        task_default_exchange='default',
        task_default_routing_key='default',
        
        # Retry settings
        task_reject_on_worker_lost=True,
        task_ignore_result=False,
        
        # Beat schedule (if using celery beat)
        beat_schedule={
            'cleanup-old-messages': {
                'task': 'app.tasks.cleanup_old_messages',
                'schedule': 3600.0,  # Every hour
            },
            'health-check': {
                'task': 'app.tasks.health_check',
                'schedule': 300.0,  # Every 5 minutes
            }
        }
    )
    
    # Configure Flask integration if app provided
    if app:
        class ContextTask(celery.Task):
            """Make celery tasks work with Flask app context"""
            def __call__(self, *args, **kwargs):
                with app.app_context():
                    return self.run(*args, **kwargs)
        
        celery.Task = ContextTask
        
        # Update config from Flask app
        celery.conf.update(app.config)
    
    return celery

def init_redis():
    """Initialize Redis connection"""
    global redis_client
    try:
        redis_url = os.getenv('REDIS_URL', 'redis://AssisText2025!Redis:@172.234.219.10:6379/0')
        redis_client = redis.from_url(redis_url, decode_responses=True)
        
        # Test connection
        redis_client.ping()
        logging.info("Redis connection initialized successfully")
        
        return redis_client
        
    except Exception as e:
        logging.error(f"Failed to initialize Redis: {str(e)}")
        redis_client = None
        return None

def init_extensions(app):
    """
    Initialize all Flask extensions with app
    
    Args:
        app: Flask application instance
    """
    global celery, redis_client
    
    # Initialize database
    db.init_app(app)
    migrate.init_app(app, db)
    
    # Initialize JWT
    jwt.init_app(app)
    
    # Initialize SocketIO
    socketio.init_app(
        app,
        cors_allowed_origins=["https://assitext.ca", "https://www.assitext.ca"],
        async_mode='threading'
    )
    
    # Initialize Mail
    mail.init_app(app)
    
    # Initialize Rate Limiter
    limiter.init_app(app)
    
    # Initialize Redis
    redis_client = init_redis()
    
    # Initialize Celery and assign to global variable
    celery = make_celery(app)
    
    # Configure JWT error handlers
    configure_jwt_handlers(app)
    
    logging.info("All extensions initialized successfully")

def configure_jwt_handlers(app):
    """Configure JWT error handlers"""
    
    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return {'message': 'Token has expired', 'error': 'token_expired'}, 401
    
    @jwt.invalid_token_loader
    def invalid_token_callback(error):
        return {'message': 'Invalid token', 'error': 'invalid_token'}, 401
    
    @jwt.unauthorized_loader
    def missing_token_callback(error):
        return {'message': 'Authorization token is required', 'error': 'authorization_required'}, 401
    
    @jwt.needs_fresh_token_loader
    def token_not_fresh_callback(jwt_header, jwt_payload):
        return {'message': 'Fresh token required', 'error': 'fresh_token_required'}, 401
    
    @jwt.revoked_token_loader
    def revoked_token_callback(jwt_header, jwt_payload):
        return {'message': 'Token has been revoked', 'error': 'token_revoked'}, 401

def get_redis():
    """Get Redis client instance"""
    global redis_client
    if redis_client is None:
        init_redis()
    return redis_client

def get_celery():
    """Get Celery instance"""
    global celery
    if celery is None:
        celery = make_celery()
    return celery

# Health check functions
def check_redis_health():
    """Check Redis connection health"""
    try:
        redis_client = get_redis()
        if redis_client:
            redis_client.ping()
            return True
        return False
    except Exception:
        return False

def check_celery_health():
    """Check Celery worker health"""
    try:
        celery_app = get_celery()
        if celery_app:
            # Check if workers are available
            inspect = celery_app.control.inspect()
            stats = inspect.stats()
            return bool(stats)
        return False
    except Exception:
        return False

def get_extension_status():
    """Get status of all extensions"""
    return {
        'database': bool(db.engine) if hasattr(db, 'engine') else False,
        'redis': check_redis_health(),
        'celery': check_celery_health(),
        'jwt': bool(jwt),
        'socketio': bool(socketio),
        'mail': bool(mail),
        'limiter': bool(limiter)
    }

# Initialize Celery at module level for worker processes
# This ensures celery is available even before Flask app initialization
if celery is None:
    try:
        celery = make_celery()
    except Exception as e:
        logging.warning(f"Failed to initialize Celery at module level: {e}")
        # This is OK - celery will be initialized when Flask app is created