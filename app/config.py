# app/config.py - Clean configuration file
import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Base configuration"""
    # Flask settings
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'GwlofZJDR5sIAVuaVLefTBBHhBYEIrwW'
    
    # Database
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # JWT settings
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or 'uRgawJTAVJLz56WEUyCxi7UoLGZuX2Dn+1kOfGNwg1GFEDIy2rGNWaf0ES1ic0rWL8gOqzzL42es0mngq2uD1w=='
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(days=30)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=90)
    
    # SignalWire configuration
    SIGNALWIRE_PROJECT_ID = os.environ.get('SIGNALWIRE_PROJECT_ID')
    SIGNALWIRE_API_TOKEN = os.environ.get('SIGNALWIRE_API_TOKEN') 
    SIGNALWIRE_SPACE_URL = os.environ.get('SIGNALWIRE_SPACE_URL')
    VERIFY_SIGNALWIRE_SIGNATURE = os.environ.get('VERIFY_SIGNALWIRE_SIGNATURE', 'True').lower() == 'true'
    
    # LLM Server configuration
    LLM_SERVER_IP = os.environ.get('LLM_SERVER_IP', '10.0.0.4')
    LLM_SERVER_PORT = int(os.environ.get('LLM_SERVER_PORT', '8080'))
    LLM_MODEL = os.environ.get('LLM_MODEL', 'dolphin-mistral:7b-v2.8')
    LLM_TIMEOUT = int(os.environ.get('LLM_TIMEOUT', '30'))
    LLM_MAX_TOKENS = int(os.environ.get('LLM_MAX_TOKENS', '150'))
    LLM_TEMPERATURE = float(os.environ.get('LLM_TEMPERATURE', '0.7'))
    
    # Application URLs
    BASE_URL = os.environ.get('BASE_URL', 'https://assitext.ca')
    BACKEND_BASE_URL = os.environ.get('BACKEND_BASE_URL', 'https://backend.assitext.ca')
    
    # Redis configuration
    REDIS_URL = os.environ.get('REDIS_URL', 'redis://:@localhost:6379/0')
    CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://:@localhost:6379/0')
    CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', 'redis://:@localhost:6379/0')
    
    # CORS settings
    CORS_ORIGINS = ['https://assitext.ca', 'https://www.assitext.ca']
    
    # Rate limiting
    MAX_DAILY_AI_RESPONSES = int(os.environ.get('MAX_DAILY_AI_RESPONSES', '100'))
    MAX_MESSAGES_PER_5MIN = int(os.environ.get('MAX_MESSAGES_PER_5MIN', '3'))
    
    # Session configuration
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = timedelta(hours=1)


class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get('DEV_DATABASE_URL') or \
        'postgresql://app_user:AssisText2025SecureDB@localhost:5432/assistext_dev'
    
    VERIFY_SIGNALWIRE_SIGNATURE = False
    SESSION_COOKIE_SECURE = False
    CORS_ORIGINS = ['http://localhost:3000', 'http://127.0.0.1:3000']


class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.environ.get('TEST_DATABASE_URL') or \
        'postgresql://app_user:AssisText2025SecureDB@localhost:5432/assistext_test'
    
    VERIFY_SIGNALWIRE_SIGNATURE = False
    WTF_CSRF_ENABLED = False


class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'postgresql://app_user:AssisText2025SecureDB@localhost:5432/assistext_prod'
    
    VERIFY_SIGNALWIRE_SIGNATURE = True
    SESSION_COOKIE_SECURE = True


# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}