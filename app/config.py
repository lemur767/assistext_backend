# app/config.py - Updated for air-gapped LLM and SignalWire
import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Base configuration with air-gapped LLM and SignalWire integration"""
    
    # Flask core settings
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'hard-to-guess-string-change-in-production'
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or 'jwt-secret-key-change-in-production'
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # SignalWire configuration (FIXED - using AUTH_TOKEN not API_TOKEN)
    SIGNALWIRE_PROJECT_ID = os.environ.get('SIGNALWIRE_PROJECT_ID')
    SIGNALWIRE_AUTH_TOKEN = os.environ.get('SIGNALWIRE_AUTH_TOKEN')  # FIXED
    SIGNALWIRE_SPACE_URL = os.environ.get('SIGNALWIRE_SPACE_URL')  # e.g., 'yourspace.signalwire.com'
    SIGNALWIRE_SIGNING_KEY = os.environ.get('SIGNALWIRE_SIGNING_KEY')  # For webhook validation
    VERIFY_SIGNALWIRE_SIGNATURE = os.environ.get('VERIFY_SIGNALWIRE_SIGNATURE', 'True') == 'True'
    
    # Air-gapped LLM server configuration (VPC internal)
    LLM_SERVER_URL = os.environ.get('LLM_SERVER_URL', 'http://10.0.0.4:8080')
    LLM_MODEL = os.environ.get('LLM_MODEL', 'llama2')  # Default model on your LLM server
    LLM_TIMEOUT = int(os.environ.get('LLM_TIMEOUT', '30'))  # Timeout in seconds
    LLM_MAX_TOKENS = int(os.environ.get('LLM_MAX_TOKENS', '150'))
    LLM_TEMPERATURE = float(os.environ.get('LLM_TEMPERATURE', '0.7'))
    
    # NO OpenAI - removed completely for air-gapped setup
    # OPENAI_API_KEY = None  # Removed
    # OPENAI_MODEL = None    # Removed
    
    # VPC Network settings (CORRECTED IPs)
    VPC_SUBNET = os.environ.get('VPC_SUBNET', '10.0.0.0/24')
    DB_SERVER_IP = os.environ.get('DB_SERVER_IP', '10.0.0.2')
    REDIS_SERVER_IP = os.environ.get('REDIS_SERVER_IP', '10.0.0.3')
    LLM_SERVER_IP = os.environ.get('LLM_SERVER_IP', '10.0.0.4')
    BACKEND_SERVER_IP = os.environ.get('BACKEND_SERVER_IP', '10.0.0.5')
    
    # Base URL for webhook configuration
    BASE_URL = os.environ.get('BASE_URL', 'https://assitext.ca')
    
    # Stripe configuration
    STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY')
    STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET')
    STRIPE_PUBLIC_KEY = os.environ.get('STRIPE_PUBLIC_KEY')
    
    # Redis and Celery configuration (VPC Redis server)
    REDIS_URL = os.environ.get('REDIS_URL', f'redis://:{os.environ.get("REDIS_PASSWORD", "")}@{os.environ.get("REDIS_SERVER_IP", "10.0.0.3")}:6379/0')
    CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL') or REDIS_URL
    CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND') or REDIS_URL
    
    # Security and encryption
    ENCRYPTION_KEY = os.environ.get('ENCRYPTION_KEY')  # For encrypting API tokens
    
    # Rate limiting and safety
    RATELIMIT_STORAGE_URL = os.environ.get('RATELIMIT_STORAGE_URL') or REDIS_URL
    RATELIMIT_STRATEGY = 'fixed-window'
    MAX_DAILY_AI_RESPONSES = int(os.environ.get('MAX_DAILY_AI_RESPONSES', '100'))
    MAX_MESSAGES_PER_5MIN = int(os.environ.get('MAX_MESSAGES_PER_5MIN', '3'))
    
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
    
    # AI and messaging settings (air-gapped specific)
    DEFAULT_AI_TEMPERATURE = float(os.environ.get('DEFAULT_AI_TEMPERATURE', '0.7'))
    DEFAULT_RESPONSE_LENGTH = int(os.environ.get('DEFAULT_RESPONSE_LENGTH', '150'))
    MAX_CONVERSATION_HISTORY = int(os.environ.get('MAX_CONVERSATION_HISTORY', '10'))  # Reduced for air-gapped
    
    # Air-gapped fallback responses when LLM server is unavailable
    FALLBACK_RESPONSES = [
        "Thanks for your message! I'll get back to you soon 😊",
        "Hi! Got your message. Let me respond properly in a bit!",
        "Hey! Just saw this. I'll message you back shortly 💕",
        "Thanks for reaching out! Give me a moment to respond properly",
        "Hi there! I'll get back to you with a proper response soon ✨"
    ]
    
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
    
    # Database (VPC database server)
    SQLALCHEMY_DATABASE_URI = os.environ.get('DEV_DATABASE_URL') or \
        f'postgresql://sms_app:{os.environ.get("DB_PASSWORD", "your_secure_password")}@{Config.DB_SERVER_IP}:5432/escort_sms_dev'
    
    # SignalWire signature verification (can be disabled for testing)
    VERIFY_SIGNALWIRE_SIGNATURE = os.environ.get('VERIFY_SIGNALWIRE_SIGNATURE', 'False') == 'True'
    
    # CORS - allow all origins in development
    CORS_ORIGINS = ['*']
    
    # Logging
    LOG_LEVEL = 'DEBUG'
    
    # Cache settings for development
    CACHE_TYPE = 'simple'
    CACHE_DEFAULT_TIMEOUT = 300
    
    # Relaxed rate limiting for development
    MAX_DAILY_AI_RESPONSES = 500
    MAX_MESSAGES_PER_5MIN = 10

class TestingConfig(Config):
    """Testing configuration"""
    
    TESTING = True
    WTF_CSRF_ENABLED = False
    
    # Database (VPC database server)
    SQLALCHEMY_DATABASE_URI = os.environ.get('TEST_DATABASE_URL') or \
        f'postgresql://sms_app:{os.environ.get("DB_PASSWORD", "your_secure_password")}@{Config.DB_SERVER_IP}:5432/escort_sms_test'
    
    # Disable SignalWire signature verification for tests
    VERIFY_SIGNALWIRE_SIGNATURE = False
    
    # Use simple cache for testing
    CACHE_TYPE = 'simple'
    
    # Shorter token expiration for testing
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=5)
    
    # Test-specific settings
    TESTING_MESSAGE_DELAY = 0  # No delay in tests
    PRESERVE_CONTEXT_ON_EXCEPTION = False
    
    # Mock LLM server for testing
    LLM_SERVER_URL = 'http://localhost:8080'  # Local test server

class ProductionConfig(Config):
    """Production configuration with enhanced security for air-gapped deployment"""
    
    DEBUG = False
    
    # Database with SSL (VPC database server)
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        f'postgresql://sms_app:{os.environ.get("DB_PASSWORD")}@{Config.DB_SERVER_IP}:5432/escort_sms_prod?sslmode=require'
    
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
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', 'https://assitext.ca').split(',')
    
    # Enable SignalWire signature verification
    VERIFY_SIGNALWIRE_SIGNATURE = True
    
    # Enhanced logging for production
    LOG_LEVEL = 'INFO'
    
    # Redis settings for production (VPC Redis server)
    CACHE_TYPE = 'redis'
    CACHE_REDIS_URL = Config.REDIS_URL
    CACHE_DEFAULT_TIMEOUT = 300
    
    # Rate limiting - more restrictive in production
    RATELIMIT_HEADERS_ENABLED = True
    
    # Air-gapped LLM settings for production
    LLM_TIMEOUT = 45  # Longer timeout for production
    LLM_MAX_TOKENS = 200  # Slightly higher for production
    
    @staticmethod
    def init_app(app):
        """Initialize production app"""
        Config.init_app(app)
        
        # Log to file in production
        import logging
        from logging.handlers import RotatingFileHandler
        
        if not os.path.exists('logs'):
            os.mkdir('logs')
        
        file_handler = RotatingFileHandler('logs/sms_ai_responder.log', maxBytes=10240000, backupCount=10)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)

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
    """Validate that all required environment variables are set for air-gapped deployment"""
    required_vars = {
        'production': [
            'SECRET_KEY',
            'JWT_SECRET_KEY', 
            'DATABASE_URL',
            'SIGNALWIRE_PROJECT_ID',
            'SIGNALWIRE_AUTH_TOKEN',  # FIXED from API_TOKEN
            'SIGNALWIRE_SPACE_URL',
            'SIGNALWIRE_SIGNING_KEY',
            'LLM_SERVER_URL',  # Required for air-gapped
            'DB_PASSWORD',
            'REDIS_PASSWORD',
            'ENCRYPTION_KEY',
            'STRIPE_SECRET_KEY'
        ],
        'development': [
            'SIGNALWIRE_PROJECT_ID',
            'SIGNALWIRE_AUTH_TOKEN',  # FIXED
            'SIGNALWIRE_SPACE_URL',
            'LLM_SERVER_URL'  # Required even in dev
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

# Air-gapped LLM helper functions
def get_llm_config():
    """Get LLM configuration for air-gapped setup"""
    return {
        'server_url': os.environ.get('LLM_SERVER_URL', 'http://10.0.1.102:8080'),
        'model': os.environ.get('LLM_MODEL', 'llama2'),
        'timeout': int(os.environ.get('LLM_TIMEOUT', '30')),
        'max_tokens': int(os.environ.get('LLM_MAX_TOKENS', '150')),
        'temperature': float(os.environ.get('LLM_TEMPERATURE', '0.7')),
        'fallback_enabled': True,  # Always use fallback for air-gapped
        'retry_attempts': int(os.environ.get('LLM_RETRY_ATTEMPTS', '2'))
    }