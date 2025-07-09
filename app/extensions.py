import os
import logging
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from flask_socketio import SocketIO
from celery import Celery

db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()
socketio = SocketIO()

# Initialize rate limiter
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["1000 per day", "100 per hour"]
)

# Initialize SocketIO with error handling
socketio = None
try:
    from flask_socketio import SocketIO
    socketio = SocketIO()
    logging.info("SocketIO imported successfully")
except ImportError as e:
    logging.warning(f"SocketIO import failed: {e}. Continuing without SocketIO.")
    socketio = None
except Exception as e:
    logging.warning(f"SocketIO initialization failed: {e}. Continuing without SocketIO.")
    socketio = None

# Initialize Redis and Celery
redis_client = None
celery = None

def make_celery(app=None):

    global celery
    
    try:
        from celery import Celery
        
        broker_url = os.getenv('CELERY_BROKER_URL', 'redis://AssisText2025!Redis:@172.234.219.10:6379/0')
        result_backend = os.getenv('CELERY_RESULT_BACKEND', 'redis://AssisText2025!Redis:@172.234.219.10:6379/0')
        
        if celery is None:
            celery = Celery(
                'assistext',
                broker=broker_url,
                backend=result_backend,
                include=['app.tasks']
            )
        
        # Configure Celery
        celery.conf.update(
            task_serializer='json',
            accept_content=['json'],
            result_serializer='json',
            timezone='America/Toronto',
            enable_utc=True,
            worker_prefetch_multiplier=1,
            task_acks_late=True,
            worker_max_tasks_per_child=1000,
            result_expires=3600,
            task_routes={
                'app.tasks.process_incoming_sms': {'queue': 'sms_processing'},
                'app.tasks.generate_ai_response': {'queue': 'ai_processing'},
                'app.tasks.send_sms_message': {'queue': 'sms_sending'},
                'app.tasks.update_message_status': {'queue': 'status_updates'},
            },
            task_default_queue='default',
            task_default_exchange='default',
            task_default_routing_key='default',
            task_reject_on_worker_lost=True,
            task_ignore_result=False,
            beat_schedule={
                'cleanup-old-messages': {
                    'task': 'app.tasks.cleanup_old_messages',
                    'schedule': 3600.0,
                },
                'health-check': {
                    'task': 'app.tasks.health_check',
                    'schedule': 300.0,
                }
            }
        )
        
        # Configure Flask integration if app provided
        if app:
            class ContextTask(celery.Task):
                def __call__(self, *args, **kwargs):
                    with app.app_context():
                        return self.run(*args, **kwargs)
            
            celery.Task = ContextTask
            celery.conf.update(app.config)
        
        return celery
        
    except ImportError as e:
        logging.warning(f"Celery import failed: {e}. Continuing without Celery.")
        return None
    except Exception as e:
        logging.warning(f"Celery initialization failed: {e}. Continuing without Celery.")
        return None

def init_redis():
    
    global redis_client
    try:
        import redis
        redis_url = os.getenv('REDIS_URL', 'redis://AssisText2025!Redis:@172.234.219.10:6379/0')
        redis_client = redis.from_url(redis_url, decode_responses=True)
        redis_client.ping()
        logging.info("Redis connection initialized successfully")
        return redis_client
    except ImportError:
        logging.warning("Redis library not available. Continuing without Redis.")
        return None
    except Exception as e:
        logging.warning(f"Redis initialization failed: {e}. Continuing without Redis.")
        return None

def init_extensions(app):
  
   
    global celery, redis_client
    
    # Initialize core extensions (these must work)
    try:
        db.init_app(app)
        migrate.init_app(app, db)
        jwt.init_app(app)
        mail.init_app(app)
        limiter.init_app(app)
        logging.info("Core extensions initialized successfully")
    except Exception as e:
        logging.error(f"Core extension initialization failed: {e}")
        raise  # These are critical, so raise the error
    
    # Initialize SocketIO (optional)
    if socketio is not None:
        try:
            socketio.init_app(
                app,
                cors_allowed_origins=["https://assitext.ca", "https://www.assitext.ca"],
                async_mode='threading'
            )
            logging.info("SocketIO initialized successfully")
        except Exception as e:
            logging.warning(f"SocketIO initialization failed: {e}. Continuing without real-time features.")
    else:
        logging.warning("SocketIO not available. Real-time features disabled.")
    
    # Initialize Redis (optional)
    try:
        redis_client = init_redis()
        if redis_client:
            logging.info("Redis initialized successfully")
    except Exception as e:
        logging.warning(f"Redis initialization failed: {e}. Continuing without caching.")
    
    # Initialize Celery (optional)
    try:
        celery = make_celery(app)
        if celery:
            logging.info("Celery initialized successfully")
    except Exception as e:
        logging.warning(f"Celery initialization failed: {e}. Continuing without background tasks.")
    
    # Configure JWT error handlers
    configure_jwt_handlers(app)
    
    logging.info("Extension initialization completed")

def configure_jwt_handlers(app):
    """Configure JWT error handlers"""
    try:
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
            
        logging.info("JWT error handlers configured")
    except Exception as e:
        logging.error(f"JWT handler configuration failed: {e}")

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

def check_redis_health():
    """Check Redis connection health"""
    try:
        client = get_redis()
        if client:
            client.ping()
            return True
        return False
    except Exception:
        return False

def check_celery_health():
    """Check Celery worker health"""
    try:
        celery_app = get_celery()
        if celery_app:
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
if celery is None:
    try:
        celery = make_celery()
    except Exception as e:
        logging.warning(f"Failed to initialize Celery at module level: {e}")
        # This is OK - celery will be initialized when Flask app is created