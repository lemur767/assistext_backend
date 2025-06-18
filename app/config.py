import os
from datetime import timedelta

class Config:
    """Application configuration"""
    
    # Flask settings
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'GwlofZJDR5sIAVuaVLefTBBHhBYEIrwW'
    
    # Database
    DATABASE_URL = os.environ.get('DATABASE_URL') or 'postgresql://app_user:AssisText2025SecureDB@localhost:5432/assistext_prod'
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # JWT settings
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or SECRET_KEY
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(days=30)
    
    # SignalWire configuration
    SIGNALWIRE_PROJECT_ID = os.environ.get('SIGNALWIRE_PROJECT_ID')
    SIGNALWIRE_API_TOKEN = os.environ.get('SIGNALWIRE_API_TOKEN') 
    SIGNALWIRE_SPACE_URL = os.environ.get('SIGNALWIRE_SPACE_URL')
    VERIFY_SIGNALWIRE_SIGNATURE = os.environ.get('VERIFY_SIGNALWIRE_SIGNATURE', 'True').lower() == 'true'
    
    # LLM Server configuration (your Ollama instance)
    LLM_SERVER_IP = os.environ.get('LLM_SERVER_IP', '10.0.0.4')
    LLM_SERVER_PORT = int(os.environ.get('LLM_SERVER_PORT', '8080'))
    LLM_SERVER_URL = f"http://{LLM_SERVER_IP}:{LLM_SERVER_PORT}"
    LLM_MODEL = os.environ.get('LLM_MODEL', 'dolphin-mistral:7b-v2.8')
    LLM_TIMEOUT = int(os.environ.get('LLM_TIMEOUT', '30'))
    LLM_MAX_TOKENS = int(os.environ.get('LLM_MAX_TOKENS', '150'))
    LLM_TEMPERATURE = float(os.environ.get('LLM_TEMPERATURE', '0.7'))
    
    # Webhook and application URLs
    BASE_URL = os.environ.get('BASE_URL', 'https://assitext.ca')
    BACKEND_BASE_URL = os.environ.get('BACKEND_BASE_URL', 'https://backend.assitext.ca', 'https://localhost:5000')
    
    # Redis configuration
    REDIS_URL = os.environ.get('REDIS_URL', 'redis://:@localhost:6379/0')
    CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', REDIS_URL)
    CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', REDIS_URL)
    
    # CORS settings
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', 'https://assitext.ca,https://www.assitext.ca').split(',')
    
    # Rate limiting and safety
    MAX_DAILY_AI_RESPONSES = int(os.environ.get('MAX_DAILY_AI_RESPONSES', '100'))
    MAX_MESSAGES_PER_5MIN = int(os.environ.get('MAX_MESSAGES_PER_5MIN', '3'))
    
    # Session configuration
    SESSION_COOKIE_SECURE = os.environ.get('FLASK_ENV') == 'production'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = timedelta(hours=1)
    
    # Application startup time
    import datetime
    START_TIME = datetime.datetime.utcnow().isoformat()


class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    VERIFY_SIGNALWIRE_SIGNATURE = False  # Disable signature verification in dev
    SESSION_COOKIE_SECURE = False


class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    VERIFY_SIGNALWIRE_SIGNATURE = True


class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    VERIFY_SIGNALWIRE_SIGNATURE = False


# Configuration mapping
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}


# Environment Variables Documentation
"""
Required Environment Variables:

# SignalWire (Required)
SIGNALWIRE_PROJECT_ID=de26db73-cf95-4570-9d3a-bb44c08eb70e
SIGNALWIRE_API_TOKEN=PTd97f3d390058b8d5cd9b1e00a176ef79e0f314b3548f5e42
SIGNALWIRE_SPACE_URL=assitext.signalwire.com

# Database (Required)
DATABASE_URL=postgresql://app_user:AssisText2025SecureDB@172.234.219.10:5432/assistext_prod

# LLM Server (Required - your Ollama instance)
LLM_SERVER_IP=10.0.0.4
LLM_SERVER_PORT=8080
LLM_MODEL=dolphin-mistral:7b-v2.8

# Application URLs (Required)
BASE_URL=https://assitext.ca
BACKEND_BASE_URL=https://backend.assitext.ca

# Optional Configuration
LLM_TIMEOUT=30
LLM_MAX_TOKENS=150
LLM_TEMPERATURE=0.7
MAX_DAILY_AI_RESPONSES=100
VERIFY_SIGNALWIRE_SIGNATURE=true
CORS_ORIGINS=https://assitext.ca,https://www.assitext.ca
"""