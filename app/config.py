"""
Working Configuration File for AssisText
app/config.py - Updated for SignalWire and LLM integration
"""
import os
from datetime import timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    """Base configuration class"""
    
    # Flask Configuration
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'GwlofZJDR5sIAVuaVLefTBBHhBYEIrwW'
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or 'uRgawJTAVJLz56WEUyCxi7UoLGZuX2Dn+1kOfGNwg1GFEDIy2rGNWaf0ES1ic0rWL8gOqzzL42es0mngq2uD1w=='
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=24)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    
    # Database Configuration
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
        'connect_args': {
            'sslmode': 'require'
        }
    }
    
    # SignalWire Configuration (Updated from Twilio)
    SIGNALWIRE_PROJECT_ID = os.environ.get('SIGNALWIRE_PROJECT_ID')
    SIGNALWIRE_API_TOKEN = os.environ.get('SIGNALWIRE_API_TOKEN') 
    SIGNALWIRE_SPACE_URL = os.environ.get('SIGNALWIRE_SPACE_URL')
    BASE_URL = os.environ.get('BASE_URL', 'https://assitext.ca')
    
    # LLM Server Configuration (Updated from OpenAI)
    LLM_SERVER_URL = os.environ.get('LLM_SERVER_URL', 'http://10.0.0.4:8080')
    LLM_MODEL = os.environ.get('LLM_MODEL', 'dolphin-mistral:7b-v2.8')
    LLM_TIMEOUT = int(os.environ.get('LLM_TIMEOUT', '30'))
    LLM_MAX_TOKENS = int(os.environ.get('LLM_MAX_TOKENS', '150'))
    LLM_TEMPERATURE = float(os.environ.get('LLM_TEMPERATURE', '0.7'))
    LLM_RETRY_ATTEMPTS = int(os.environ.get('LLM_RETRY_ATTEMPTS', '2'))
    
    # Stripe Configuration
    STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY')
    STRIPE_PUBLIC_KEY = os.environ.get('STRIPE_PUBLIC_KEY')
    STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET')
    
    # Celery Configuration
    CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://AssisText2025!Redis:@172.234.219.10:6379/0')
    CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', 'redis://AssisText2025!Redis:@172.234.219.10:6379/0')
    
    # Redis Configuration
    REDIS_URL = os.environ.get('REDIS_URL', 'redis://AssisText2025!Redis:@172.234.219.10:6379/0')
    
    # Rate Limiting Configuration
    RATELIMIT_STORAGE_URL = os.environ.get('RATELIMIT_STORAGE_URL', 'redis://AssisText2025!Redis:@172.234.219.10:6379/1')
    MAX_DAILY_AI_RESPONSES = int(os.environ.get('MAX_DAILY_AI_RESPONSES', '100'))
    MAX_MESSAGES_PER_5MIN = int(os.environ.get('MAX_MESSAGES_PER_5MIN', '3'))
    
    # Mail Configuration
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', '587'))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'True').lower() == 'true'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@assitext.ca')
    
    # Security Configuration
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = timedelta(hours=1)
    
    # CORS Configuration
    CORS_ORIGINS = ['https://assitext.ca', 'https://www.assitext.ca']
    
    # Logging Configuration
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')


class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    TESTING = False
    
    # Development Database
    SQLALCHEMY_DATABASE_URI = os.environ.get('DEV_DATABASE_URL') or \
        'postgresql://app_user:AssisText2025!SecureDB@172.234.219.10:5432/assistext_dev?sslmode=require'
    
    # Development overrides
    SESSION_COOKIE_SECURE = False  # Allow HTTP in development
    CORS_ORIGINS = ['http://localhost:3000', 'http://localhost:5173', 'https://assitext.ca', 'https://www.assitext.ca']
    
    # Development LLM (might be different)
    LLM_SERVER_URL = os.environ.get('LLM_SERVER_URL', 'http://localhost:8080')
    
    # Development SignalWire (might use test credentials)
    BASE_URL = os.environ.get('BASE_URL', 'https://assitext.ca')  # Still use production URL for webhooks


class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    DEBUG = False
    
    # Test Database
    SQLALCHEMY_DATABASE_URI = os.environ.get('TEST_DATABASE_URL') or \
        'postgresql://app_user:AssisText2025!SecureDB@172.234.219.10:5432/assistext_test?sslmode=require'
    
    # Disable CSRF in testing
    WTF_CSRF_ENABLED = False
    
    # Test overrides
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=5)  # Shorter for testing
    
    # Mock external services in testing
    LLM_SERVER_URL = 'http://mock-llm:8080'
    SIGNALWIRE_PROJECT_ID = 'test-project'
    SIGNALWIRE_API_TOKEN = 'test-token'
    SIGNALWIRE_SPACE_URL = 'test.signalwire.com'
    
    # Use in-memory database for faster tests
    # SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'


class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    TESTING = False
    
    # Production Database
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'postgresql://app_user:AssisText2025!SecureDB@172.234.219.10:5432/assistext_prod?sslmode=require'
    
    # Production security
    SESSION_COOKIE_SECURE = True
    
    # Production logging
    LOG_LEVEL = 'WARNING'
    
    # Production rate limiting (stricter)
    MAX_DAILY_AI_RESPONSES = int(os.environ.get('MAX_DAILY_AI_RESPONSES', '50'))
    MAX_MESSAGES_PER_5MIN = int(os.environ.get('MAX_MESSAGES_PER_5MIN', '2'))


# Configuration mapping dictionary - THIS IS WHAT GETS IMPORTED
config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': ProductionConfig  # Default to production for safety
}

# Alternative name for backward compatibility
config_map = config

def get_config(config_name=None):
    """
    Get configuration class by name
    
    Args:
        config_name: Configuration name ('development', 'testing', 'production')
        
    Returns:
        Configuration class
    """
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'production')
    
    return config.get(config_name, config['default'])