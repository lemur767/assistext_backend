# =============================================================================
# app/config.py
"""
CONFIGURATION CLASSES - CORRECTED VERSION
Environment-specific configurations based on actual .env structure
"""
import os
from datetime import timedelta


class Config:
    """Base configuration using actual environment variable names"""
    
    # Flask Configuration
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-key-change-in-production')
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', SECRET_KEY)
    
    # PostgreSQL Database Configuration
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'postgresql://username:password@localhost/sms_ai_dev')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
        'pool_size': 10,
        'max_overflow': 20
    }
    
    # JWT Configuration
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    
    # SignalWire Configuration (actual variable names)
    SIGNALWIRE_PROJECT_ID = os.getenv('SIGNALWIRE_PROJECT_ID')
    SIGNALWIRE_API_TOKEN = os.getenv('SIGNALWIRE_API_TOKEN')
    SIGNALWIRE_SPACE_URL = os.getenv('SIGNALWIRE_SPACE_URL')
    
    # LLM Configuration
    LLM_SERVER_URL = os.getenv('LLM_SERVER_URL', 'http://10.0.0.102:8080/v1/chat/completions')
    LLM_API_KEY = os.getenv('LLM_API_KEY', 'local-api-key')
    LLM_MODEL = os.getenv('LLM_MODEL', 'llama2')
    
    # Stripe Configuration
    STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY')
    STRIPE_PUBLIC_KEY = os.getenv('STRIPE_PUBLIC_KEY')
    STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET')
    
    # Redis Configuration
    REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', REDIS_URL)
    CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', REDIS_URL)
    
    # Application URLs
    FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:3000')
    BACKEND_URL = os.getenv('BACKEND_URL', 'http://localhost:5000')
    WEBHOOK_BASE_URL = os.getenv('WEBHOOK_BASE_URL', BACKEND_URL)
    
    # Security
    VERIFY_WEBHOOK_SIGNATURES = os.getenv('VERIFY_WEBHOOK_SIGNATURES', 'True').lower() == 'true'
    WEBHOOK_SECRET = os.getenv('WEBHOOK_SECRET', 'your-webhook-secret-key')
    
    # Rate Limiting
    RATELIMIT_STORAGE_URL = REDIS_URL
    RATELIMIT_DEFAULT = "1000 per hour"


class DevelopmentConfig(Config):
    """Development environment configuration"""
    DEBUG = True
    TESTING = False
    RATELIMIT_ENABLED = False
    
    # Use development database
    SQLALCHEMY_DATABASE_URI = os.getenv('DEV_DATABASE_URL', 'postgresql://username:password@localhost/sms_ai_dev')
    
    # Relaxed security for development
    SESSION_COOKIE_SECURE = False
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=8)


class TestingConfig(Config):
    """Testing environment configuration"""
    DEBUG = False
    TESTING = True
    RATELIMIT_ENABLED = False
    
    # Use test database
    SQLALCHEMY_DATABASE_URI = os.getenv('TEST_DATABASE_URL', 'postgresql://username:password@localhost/sms_ai_test')
    
    # Disable external services in testing
    SIGNALWIRE_PROJECT_ID = 'test-project'
    SIGNALWIRE_API_TOKEN = 'test-token'
    STRIPE_SECRET_KEY = 'sk_test_fake'


class ProductionConfig(Config):
    """Production environment configuration"""
    DEBUG = False
    TESTING = False
    RATELIMIT_ENABLED = True
    
    # Security
    SESSION_COOKIE_SECURE = True
    
    # Database connection pooling for production
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
        'pool_size': 20,
        'max_overflow': 40
    }


# Configuration mapping
config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': ProductionConfig
}

