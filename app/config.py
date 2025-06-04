# app/config.py - Updated for SignalWire (Twilio completely removed)
import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Base configuration with SignalWire integration"""
    
    # Flask core settings
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'hard-to-guess-string-change-in-production'
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or 'jwt-secret-key-change-in-production'
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # SignalWire configuration (replaces Twilio)
    SIGNALWIRE_PROJECT_ID = os.environ.get('SIGNALWIRE_PROJECT_ID')
    SIGNALWIRE_API_TOKEN = os.environ.get('SIGNALWIRE_API_TOKEN')
    SIGNALWIRE_SPACE_URL = os.environ.get('SIGNALWIRE_SPACE_URL')  # e.g., 'yourspace.signalwire.com'
    VERIFY_SIGNALWIRE_SIGNATURE = os.environ.get('VERIFY_SIGNALWIRE_SIGNATURE', 'True') == 'True'
    
    # Base URL for webhook configuration
    BASE_URL = os.environ.get('BASE_URL', 'https://yourapp.com')
    
    # OpenAI configuration
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
    OPENAI_MODEL = os.environ.get('OPENAI_MODEL', 'gpt-4')
  
    
    # Stripe configuration
    STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY')
    STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET')
    STRIPE_PUBLIC_KEY = os.environ.get('STRIPE_PUBLIC_KEY')
    
    # Redis and Celery configuration
    REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
    CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL') or REDIS_URL
    CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND') or REDIS_URL
    
    # Security and encryption
    ENCRYPTION_KEY = os.environ.get('ENCRYPTION_KEY')  # For encrypting SignalWire API tokens
    
    # Rate limiting
    RATELIMIT_STORAGE_URL = os.environ.get('RATELIMIT_STORAGE_URL') or REDIS_URL
    RATELIMIT_STRATEGY = 'fixed-window'
    
    # CORS settings
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', '*').split(',')
    CORS_SUPPORTS_CREDENTIALS = True
    
    # Session settings
    SESSION_COOKIE_SECURE = False  # Will be True in production
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = 3600
    
    # Logging
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FORMAT = '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
    
    # Email configuration (for notifications)
    MAIL_SERVER = os.environ.get('MAIL_SERVER')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'True') == 'True'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER')
    
    # File upload settings
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    UPLOAD_FOLDER = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'uploads')
    
    # AI and messaging settings
    DEFAULT_AI_TEMPERATURE = float(os.environ.get('DEFAULT_AI_TEMPERATURE', '0.7'))
    DEFAULT_RESPONSE_LENGTH = int(os.environ.get('DEFAULT_RESPONSE_LENGTH', '150'))
    MAX_CONVERSATION_HISTORY = int(os.environ.get('MAX_CONVERSATION_HISTORY', '20'))
    
    # Subscription and billing settings
    FREE_TRIAL_DAYS = int(os.environ.get('FREE_TRIAL_DAYS', '7'))
    DEFAULT_MESSAGE_LIMIT = int(os.environ.get('DEFAULT_MESSAGE_LIMIT', '100'))
    
    @staticmethod
    def init_app(app):
        """Initialize application with config"""
        pass

class DevelopmentConfig(Config):
    """Development configuration"""
    
    DEBUG = True
    
    # Database
    SQLALCHEMY_DATABASE_URI = os.environ.get('DEV_DATABASE_URL') or \
        'postgresql://postgres:plmnko1423$$$@localhost:5432/assistext_dev'
    
    # SignalWire signature verification (can be disabled for testing)
    VERIFY_SIGNALWIRE_SIGNATURE = os.environ.get('VERIFY_SIGNALWIRE_SIGNATURE', 'False') == 'True'
    
    # CORS - allow all origins in development
    CORS_ORIGINS = ['*']
    
    # Logging
    LOG_LEVEL = 'DEBUG'
    
    # Cache settings for development
    CACHE_TYPE = 'simple'
    CACHE_DEFAULT_TIMEOUT = 300

class TestingConfig(Config):
    """Testing configuration"""
    
    TESTING = True
    WTF_CSRF_ENABLED = False
    
    # Database
    SQLALCHEMY_DATABASE_URI = os.environ.get('TEST_DATABASE_URL') or \
        'postgresql://postgres:password@localhost/sms_ai_test'
    
    # Disable SignalWire signature verification for tests
    VERIFY_SIGNALWIRE_SIGNATURE = False
    
    # Use in-memory cache for testing
    CACHE_TYPE = 'simple'
    
    # Shorter token expiration for testing
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=5)
    
    # Test-specific settings
    TESTING_MESSAGE_DELAY = 0  # No delay in tests
    PRESERVE_CONTEXT_ON_EXCEPTION = False

class ProductionConfig(Config):
    """Production configuration with enhanced security"""
    
    DEBUG = False
    
    # Database with SSL
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_recycle': 3600,
        'pool_pre_ping': True,
        'pool_size': 10,
        'max_overflow': 20,
        'connect_args': {
            'sslmode': 'require',
            'connect_timeout': 10,
        }
    }
    
    # Security settings
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # CORS - restrict to specific domains
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', '').split(',')
    
    # Enable SignalWire signature verification
    VERIFY_SIGNALWIRE_SIGNATURE = True
    
    # Enhanced logging for production
    LOG_LEVEL = 'INFO'
    
    # Redis settings for production
    CACHE_TYPE = 'redis'
    CACHE_REDIS_URL = os.environ.get('REDIS_URL')
    CACHE_DEFAULT_TIMEOUT = 300
    
    # Rate limiting - more restrictive in production
    RATELIMIT_HEADERS_ENABLED = True
    
    @staticmethod
    def init_app(app):
        """Initialize production app"""
        Config.init_app(app)
        
        # Log to syslog in production
        import logging
        from logging.handlers import SysLogHandler
        
        syslog_handler = SysLogHandler()
        syslog_handler.setLevel(logging.WARNING)
        app.logger.addHandler(syslog_handler)

class StagingConfig(ProductionConfig):
    """Staging configuration - like production but with debug info"""
    
    DEBUG = False
    LOG_LEVEL = 'DEBUG'
    
    # Less restrictive CORS for staging
    CORS_ORIGINS = ['*']
    
    # Can disable signature verification for staging tests
    VERIFY_SIGNALWIRE_SIGNATURE = os.environ.get('VERIFY_SIGNALWIRE_SIGNATURE', 'True') == 'True'

# Configuration mapping
config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'staging': StagingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}

# Helper function to get config
def get_config():
    """Get configuration based on environment"""
    return config[os.getenv('FLASK_ENV', 'default')]

# Validation function for required environment variables
def validate_config():
    """Validate that all required environment variables are set"""
    required_vars = {
        'production': [
            'SECRET_KEY',
            'JWT_SECRET_KEY', 
            'DATABASE_URL',
            'SIGNALWIRE_PROJECT_ID',
            'SIGNALWIRE_API_TOKEN',
            'SIGNALWIRE_SPACE_URL',
            'ENCRYPTION_KEY',
            'STRIPE_SECRET_KEY',
            'OPENAI_API_KEY'
        ],
        'development': [
            'SIGNALWIRE_PROJECT_ID',
            'SIGNALWIRE_API_TOKEN', 
            'SIGNALWIRE_SPACE_URL'
        ],
        'testing': []
    }
    
    env = os.getenv('FLASK_ENV', 'development')
    missing_vars = []
    
    for var in required_vars.get(env, []):
        if not os.environ.get(var):
            missing_vars.append(var)
    
    if missing_vars:
        raise EnvironmentError(
            f"Missing required environment variables for {env}: {', '.join(missing_vars)}"
        )
    
    return True

# SignalWire webhook URLs helper
def get_webhook_urls():
    """Get properly formatted webhook URLs for SignalWire configuration"""
    base_url = os.environ.get('BASE_URL', 'https://assitext.ca')
    
    return {
        'sms_url': f"{base_url}/api/webhooks/sms",
        'voice_url': f"{base_url}/api/webhooks/voice", 
        'status_callback_url': f"{base_url}/api/webhooks/message-status"
    }
