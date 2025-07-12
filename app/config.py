"""
Production-Ready Configuration for AssisText Backend
app/config.py - Configured with actual environment variables and infrastructure

This configuration matches your actual environment variables from the project context
and includes proper SignalWire integration, PostgreSQL database, and LLM server setup.
"""

import os
import secrets
from datetime import timedelta
from typing import Dict, Type, Optional, List
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class ConfigurationError(Exception):
    """Custom exception for configuration errors"""
    pass

class BaseConfig:
    """Base configuration class with actual environment variables"""
    
    # =============================================================================
    # CORE FLASK CONFIGURATION
    # =============================================================================
    
    # Application secrets - using your actual values
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'eGJheGYyeGZmbHgxNng5NXhjYXhiM3hkZnhlNnhiOHhiOXg5N3g4ZXhmNUJwU3gxMw=='
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or 'xbaxf2xfflx16x95xcaxb3xdfxe6xb5!x1excaxd6x15Cxd7x97x08xb9x97x8exf5BpSx13'
    
    # JWT Configuration
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=24)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    JWT_ALGORITHM = 'HS256'
    JWT_ERROR_MESSAGE_KEY = 'message'
    
    # Application URLs - using your actual domains
    BASE_URL = os.environ.get('BASE_URL', 'https://backend.assitext.ca')
    FRONTEND_URL = os.environ.get('FRONTEND_URL', 'https://assitext.ca')
    
    # Security Configuration
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'True').lower() == 'true'
    SESSION_COOKIE_HTTPONLY = os.environ.get('SESSION_COOKIE_HTTPONLY', 'True').lower() == 'true'
    SESSION_COOKIE_SAMESITE = os.environ.get('SESSION_COOKIE_SAMESITE', 'Lax')
    PERMANENT_SESSION_LIFETIME = timedelta(seconds=int(os.environ.get('PERMANENT_SESSION_LIFETIME', '3600')))
    
    # =============================================================================
    # DATABASE CONFIGURATION - YOUR ACTUAL POSTGRESQL
    # =============================================================================
    
    # Using your actual database configuration
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'postgresql://app_user:Assistext2025Secure@localhost:5432/assistext_prod'
    
    # Alternative database component variables
    DB_HOST = os.environ.get('DB_HOST', 'localhost')
    DB_PORT = int(os.environ.get('DB_PORT', '5432'))
    DB_USER = os.environ.get('DB_USER', 'app_user')
    DB_PASSWORD = os.environ.get('DB_PASSWORD', 'Assistext2025Secure')
    DB_NAME = os.environ.get('DB_NAME', 'assistext_prod')
    
    # SQLAlchemy configuration for production
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_RECORD_QUERIES = True
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 20,
        'pool_recycle': 3600,
        'pool_pre_ping': True,
        'pool_timeout': 30,
        'max_overflow': 30,
        'connect_args': {
            'sslmode': 'prefer',  # Adjust based on your PostgreSQL setup
            'connect_timeout': 10,
            'application_name': 'assistext_backend'
        }
    }
    
    # =============================================================================
    # SIGNALWIRE CONFIGURATION - YOUR ACTUAL CREDENTIALS
    # =============================================================================
    
    # SignalWire credentials - using your actual values
    SIGNALWIRE_PROJECT_ID = os.environ.get('SIGNALWIRE_PROJECT_ID') or 'de26db73-cf95-4570-9d3a-bb44c08eb70e'
    SIGNALWIRE_AUTH_TOKEN = os.environ.get('SIGNALWIRE_AUTH_TOKEN') or 'PTd97f3d390058b8d5cd9b1e00a176ef79e0f314b3548f5e42'
    SIGNALWIRE_SPACE_URL = os.environ.get('SIGNALWIRE_SPACE_URL') or 'assitext.signalwire.com'
    
    # Alternative naming for backward compatibility
    SIGNALWIRE_API_TOKEN = SIGNALWIRE_AUTH_TOKEN  # Same value, different name
    SIGNALWIRE_PROJECT = SIGNALWIRE_PROJECT_ID    # Same value, different name
    SIGNALWIRE_SPACE = SIGNALWIRE_SPACE_URL       # Same value, different name
    
    # SignalWire API configuration
    SIGNALWIRE_API_VERSION = '2010-04-01'
    SIGNALWIRE_TIMEOUT = 30
    SIGNALWIRE_RETRY_ATTEMPTS = 3
    
    # Webhook configuration
    WEBHOOK_BASE_URL = BASE_URL
    WEBHOOK_VALIDATION = os.environ.get('WEBHOOK_VALIDATION', 'True').lower() == 'true'
    WEBHOOK_SECRET = os.environ.get('WEBHOOK_SECRET') or secrets.token_hex(32)
    
    # =============================================================================
    # LLM SERVER CONFIGURATION - YOUR ACTUAL LLM SERVER
    # =============================================================================
    
    # LLM server configuration - using your actual server
    LLM_SERVER_URL = os.environ.get('LLM_SERVER_URL', 'http://10.0.0.4:8080')
    LLM_SERVER_IP = os.environ.get('LLM_SERVER_IP', '10.0.0.4')
    LLM_MODEL = os.environ.get('LLM_MODEL', 'dolphin-mistral:7b-v2.8')
    
    # LLM request configuration
    LLM_TIMEOUT = int(os.environ.get('LLM_TIMEOUT', '30'))
    LLM_MAX_TOKENS = int(os.environ.get('LLM_MAX_TOKENS', '150'))
    LLM_TEMPERATURE = float(os.environ.get('LLM_TEMPERATURE', '0.7'))
    LLM_RETRY_ATTEMPTS = int(os.environ.get('LLM_RETRY_ATTEMPTS', '2'))
    
    # AI response configuration
    AI_RESPONSE_MAX_LENGTH = int(os.environ.get('AI_RESPONSE_MAX_LENGTH', '160'))
    AI_RESPONSE_STYLE = os.environ.get('AI_RESPONSE_STYLE', 'professional')
    
    # =============================================================================
    # REDIS AND CELERY CONFIGURATION - YOUR ACTUAL REDIS
    # =============================================================================
    
    # Redis configuration - using your actual Redis instance
    REDIS_URL = os.environ.get('REDIS_URL', 'redis://:Assistext2025Secure@localhost:6379/0')
    REDIS_PASSWORD = os.environ.get('REDIS_PASSWORD', 'Assistext2025Secure')
    REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
    REDIS_PORT = int(os.environ.get('REDIS_PORT', '6379'))
    
    # Celery configuration - using your actual Redis setup
    CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://:Assistext2025Secure@localhost:6379/0')
    CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', 'redis://:Assistext2025Secure@localhost:6379/0')
    
    # Celery task configuration
    CELERY_TASK_SERIALIZER = 'json'
    CELERY_RESULT_SERIALIZER = 'json'
    CELERY_ACCEPT_CONTENT = ['json']
    CELERY_TIMEZONE = 'UTC'
    CELERY_ENABLE_UTC = True
    
    # Task routing for performance
    CELERY_ROUTES = {
        'app.tasks.send_sms': {'queue': 'sms'},
        'app.tasks.process_ai_response': {'queue': 'ai'},
        'app.tasks.handle_webhook': {'queue': 'webhooks'},
        'app.tasks.process_analytics': {'queue': 'analytics'},
    }
    
    # =============================================================================
    # RATE LIMITING CONFIGURATION - YOUR ACTUAL REDIS
    # =============================================================================
    
    # Rate limiting using your Redis instance
    RATELIMIT_STORAGE_URL = os.environ.get('RATELIMIT_STORAGE_URL', 'redis://:Assistext2025Secure@localhost:6379/1')
    RATELIMIT_STRATEGY = 'fixed-window'
    RATELIMIT_HEADERS_ENABLED = True
    
    # Rate limits - using your actual values
    MAX_DAILY_AI_RESPONSES = int(os.environ.get('MAX_DAILY_AI_RESPONSES', '100'))
    MAX_MESSAGES_PER_5MIN = int(os.environ.get('MAX_MESSAGES_PER_5MIN', '5'))
    MAX_API_REQUESTS_PER_MINUTE = int(os.environ.get('MAX_API_REQUESTS_PER_MINUTE', '60'))
    
    # =============================================================================
    # CORS CONFIGURATION - YOUR ACTUAL DOMAINS
    # =============================================================================
    
    # CORS origins - using your actual domains and development ports
    _cors_origins_str = os.environ.get('CORS_ORIGINS', 
        'http://localhost:3000,http://localhost:3001,http://localhost:5173,https://assitext.ca,https://www.assitext.ca')
    CORS_ORIGINS = [origin.strip() for origin in _cors_origins_str.split(',')]
    
    # CORS configuration
    CORS_ALLOW_HEADERS = ['Content-Type', 'Authorization', 'X-Requested-With', 'Accept', 'Origin']
    CORS_METHODS = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS']
    CORS_SUPPORTS_CREDENTIALS = True
    
    # =============================================================================
    # MAIL CONFIGURATION
    # =============================================================================
    
    # Email settings for notifications
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', '587'))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'True').lower() == 'true'
    MAIL_USE_SSL = os.environ.get('MAIL_USE_SSL', 'False').lower() == 'true'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@assitext.ca')
    
    # =============================================================================
    # LOGGING CONFIGURATION
    # =============================================================================
    
    # Logging settings - using your actual log level
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FORMAT = '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
    LOG_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'
    
    # =============================================================================
    # STRIPE CONFIGURATION (IF USING BILLING)
    # =============================================================================
    
    # Stripe for billing (optional)
    STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY')
    STRIPE_PUBLIC_KEY = os.environ.get('STRIPE_PUBLIC_KEY')
    STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET')
    
    # =============================================================================
    # FEATURE FLAGS
    # =============================================================================
    
    # Feature toggles
    FEATURE_AI_RESPONSES = os.environ.get('FEATURE_AI_RESPONSES', 'True').lower() == 'true'
    FEATURE_MMS_SUPPORT = os.environ.get('FEATURE_MMS_SUPPORT', 'True').lower() == 'true'
    FEATURE_ANALYTICS = os.environ.get('FEATURE_ANALYTICS', 'True').lower() == 'true'
    FEATURE_BILLING = os.environ.get('FEATURE_BILLING', 'False').lower() == 'true'
    FEATURE_WEBHOOKS = os.environ.get('FEATURE_WEBHOOKS', 'True').lower() == 'true'
    
    # =============================================================================
    # VALIDATION METHODS
    # =============================================================================
    
    @classmethod
    def validate_signalwire_config(cls) -> bool:
        """Validate SignalWire configuration"""
        required = [cls.SIGNALWIRE_PROJECT_ID, cls.SIGNALWIRE_AUTH_TOKEN, cls.SIGNALWIRE_SPACE_URL]
        return all(required)
    
    @classmethod
    def validate_database_config(cls) -> bool:
        """Validate database configuration"""
        return bool(cls.SQLALCHEMY_DATABASE_URI)
    
    @classmethod
    def validate_redis_config(cls) -> bool:
        """Validate Redis configuration"""
        return bool(cls.REDIS_URL)
    
    @classmethod
    def get_signalwire_client_config(cls) -> Dict[str, str]:
        """Get SignalWire client configuration"""
        return {
            'project_id': cls.SIGNALWIRE_PROJECT_ID,
            'auth_token': cls.SIGNALWIRE_AUTH_TOKEN,
            'space_url': cls.SIGNALWIRE_SPACE_URL,
            'timeout': cls.SIGNALWIRE_TIMEOUT,
        }
    
    @classmethod
    def get_database_url(cls) -> str:
        """Get formatted database URL"""
        if cls.SQLALCHEMY_DATABASE_URI:
            return cls.SQLALCHEMY_DATABASE_URI
        else:
            return f"postgresql://{cls.DB_USER}:{cls.DB_PASSWORD}@{cls.DB_HOST}:{cls.DB_PORT}/{cls.DB_NAME}"


class DevelopmentConfig(BaseConfig):
    """Development environment configuration"""
    
    DEBUG = True
    TESTING = False
    
    # Development database (can use same as production for consistency)
    SQLALCHEMY_DATABASE_URI = os.environ.get('DEV_DATABASE_URL') or \
        f"postgresql://{BaseConfig.DB_USER}:{BaseConfig.DB_PASSWORD}@{BaseConfig.DB_HOST}:{BaseConfig.DB_PORT}/assistext_dev"
    
    # Relaxed security for development
    SESSION_COOKIE_SECURE = False  # Allow HTTP in development
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=8)  # Shorter tokens for development
    
    # Development logging
    LOG_LEVEL = 'DEBUG'
    
    # More permissive rate limits for development
    MAX_DAILY_AI_RESPONSES = int(os.environ.get('MAX_DAILY_AI_RESPONSES', '500'))
    MAX_MESSAGES_PER_5MIN = int(os.environ.get('MAX_MESSAGES_PER_5MIN', '10'))
    
    # Disable webhook validation in development
    WEBHOOK_VALIDATION = False
    
    # CORS - include development ports
    CORS_ORIGINS = [
        'http://localhost:3000',
        'http://localhost:3001', 
        'http://localhost:5173',
        'http://127.0.0.1:3000',
        'http://127.0.0.1:5173',
        'https://assitext.ca',
        'https://www.assitext.ca'
    ]


class TestingConfig(BaseConfig):
    """Testing environment configuration"""
    
    DEBUG = False
    TESTING = True
    
    # Test database
    SQLALCHEMY_DATABASE_URI = os.environ.get('TEST_DATABASE_URL') or \
        f"postgresql://{BaseConfig.DB_USER}:{BaseConfig.DB_PASSWORD}@{BaseConfig.DB_HOST}:{BaseConfig.DB_PORT}/assistext_test"
    
    # Disable external services in tests
    CELERY_TASK_ALWAYS_EAGER = True  # Execute tasks synchronously
    CELERY_TASK_EAGER_PROPAGATES = True
    
    # Mock configurations for testing
    SIGNALWIRE_PROJECT_ID = 'test-project-id'
    SIGNALWIRE_AUTH_TOKEN = 'test-auth-token'
    SIGNALWIRE_SPACE_URL = 'test.signalwire.com'
    
    LLM_SERVER_URL = 'http://mock-llm-server:8080'
    
    # Disable rate limiting in tests
    RATELIMIT_ENABLED = False
    
    # Fast JWT tokens for testing
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=5)
    
    # Simplified SQLAlchemy config for testing
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': False,
        'pool_size': 5,
        'max_overflow': 10
    }


class ProductionConfig(BaseConfig):
    """Production environment configuration"""
    
    DEBUG = False
    TESTING = False
    
    # Production database - use your actual production database
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'postgresql://app_user:Assistext2025Secure@localhost:5432/assistext_prod'
    
    # Strict security in production
    SESSION_COOKIE_SECURE = True
    WEBHOOK_VALIDATION = True
    
    # Production logging
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    
    # Production rate limiting - using your actual values
    MAX_DAILY_AI_RESPONSES = int(os.environ.get('MAX_DAILY_AI_RESPONSES', '100'))
    MAX_MESSAGES_PER_5MIN = int(os.environ.get('MAX_MESSAGES_PER_5MIN', '5'))
    
    # Production error handling
    PROPAGATE_EXCEPTIONS = False
    
    # Production CORS - only your actual domains
    CORS_ORIGINS = [
        'https://assitext.ca',
        'https://www.assitext.ca',
        'https://backend.assitext.ca'
    ]
    
    @classmethod
    def validate_production_config(cls) -> None:
        """Validate critical production configuration"""
        errors = []
        
        if not cls.validate_signalwire_config():
            errors.append("SignalWire configuration incomplete")
        
        if not cls.validate_database_config():
            errors.append("Database configuration missing")
        
        if not cls.validate_redis_config():
            errors.append("Redis configuration missing")
        
        if not cls.SECRET_KEY or len(cls.SECRET_KEY) < 32:
            errors.append("SECRET_KEY must be at least 32 characters")
        
        if not cls.JWT_SECRET_KEY or len(cls.JWT_SECRET_KEY) < 32:
            errors.append("JWT_SECRET_KEY must be at least 32 characters")
        
        if errors:
            raise ConfigurationError(f"Production configuration errors: {', '.join(errors)}")


# =============================================================================
# CONFIGURATION REGISTRY
# =============================================================================

# Configuration mapping - this is what gets imported by the app
config: Dict[str, Type[BaseConfig]] = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': ProductionConfig  # Safe default
}

# Backward compatibility aliases
config_map = config
configurations = config


def get_config(config_name: Optional[str] = None) -> Type[BaseConfig]:
    """
    Get configuration class by name with environment detection
    
    Args:
        config_name: Configuration name ('development', 'testing', 'production')
        
    Returns:
        Configuration class
        
    Raises:
        ConfigurationError: If configuration is invalid
    """
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'production')
    
    config_class = config.get(config_name, config['default'])
    
    # Validate production configuration
    if config_name == 'production' and hasattr(config_class, 'validate_production_config'):
        try:
            config_class.validate_production_config()
        except ConfigurationError as e:
            print(f"⚠️ Production configuration warning: {e}")
            # Don't raise in production to allow startup, but log the warning
    
    return config_class


def create_config_object(config_name: Optional[str] = None) -> BaseConfig:
    """
    Create configuration object instance
    
    Args:
        config_name: Configuration name
        
    Returns:
        Configuration object instance
    """
    config_class = get_config(config_name)
    return config_class()


# =============================================================================
# CONFIGURATION VALIDATION UTILITIES
# =============================================================================

def validate_environment() -> Dict[str, bool]:
    """
    Validate current environment configuration
    
    Returns:
        Dictionary of validation results
    """
    config_name = os.environ.get('FLASK_ENV', 'production')
    config_class = get_config(config_name)
    
    return {
        'signalwire': config_class.validate_signalwire_config(),
        'database': config_class.validate_database_config(),
        'redis': config_class.validate_redis_config(),
        'llm_server': bool(config_class.LLM_SERVER_URL),
        'secrets': bool(config_class.SECRET_KEY and config_class.JWT_SECRET_KEY),
    }


def get_config_summary() -> Dict[str, any]:
    """
    Get summary of current configuration (without sensitive data)
    
    Returns:
        Configuration summary
    """
    config_name = os.environ.get('FLASK_ENV', 'production')
    config_class = get_config(config_name)
    
    return {
        'environment': config_name,
        'debug': getattr(config_class, 'DEBUG', False),
        'testing': getattr(config_class, 'TESTING', False),
        'signalwire_configured': config_class.validate_signalwire_config(),
        'database_configured': config_class.validate_database_config(),
        'redis_configured': config_class.validate_redis_config(),
        'llm_server': config_class.LLM_SERVER_URL,
        'base_url': config_class.BASE_URL,
        'frontend_url': config_class.FRONTEND_URL,
        'features': {
            'ai_responses': config_class.FEATURE_AI_RESPONSES,
            'mms_support': config_class.FEATURE_MMS_SUPPORT,
            'analytics': config_class.FEATURE_ANALYTICS,
            'billing': config_class.FEATURE_BILLING,
            'webhooks': config_class.FEATURE_WEBHOOKS,
        },
        'rate_limits': {
            'daily_ai_responses': config_class.MAX_DAILY_AI_RESPONSES,
            'messages_per_5min': config_class.MAX_MESSAGES_PER_5MIN,
        }
    }


# Export for easy imports
__all__ = [
    'config', 'config_map', 'configurations',
    'BaseConfig', 'DevelopmentConfig', 'TestingConfig', 'ProductionConfig',
    'get_config', 'create_config_object', 'validate_environment', 'get_config_summary',
    'ConfigurationError'
]