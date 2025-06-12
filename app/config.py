import os
from datetime import timedelta
from dotenv import load_dotenv
import urllib.parse

load_dotenv()

def encode_database_url(url):
    """Properly encode database URL with special characters"""
    if not url:
        return url
    
    # Parse the URL
    parts = urllib.parse.urlparse(url)
    
    # If password contains special characters, encode them
    if parts.password and any(char in parts.password for char in ['!', '@', '#', '$', '%', '^', '&', '*']):
        # Reconstruct with encoded password
        encoded_password = urllib.parse.quote(parts.password, safe='')
        netloc = f"{parts.username}:{encoded_password}@{parts.hostname}"
        if parts.port:
            netloc += f":{parts.port}"
        
        encoded_url = urllib.parse.urlunparse((
            parts.scheme,
            netloc,
            parts.path,
            parts.params,
            parts.query,
            parts.fragment
        ))
        return encoded_url
    
    return url

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'GwlofZJDR5sIAVuaVLefTBBHhBYEIrwW'
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or 'uRgawJTAVJLz56WEUyCxi7UoLGZuX2Dn+1kOfGNwg1GFEDIy2rGNWaf0ES1ic0rWL8gOqzzL42es0mngq2uD1w=='
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # SignalWire configuration
    SIGNALWIRE_PROJECT_ID = os.environ.get('SIGNALWIRE_PROJECT_ID')
    SIGNALWIRE_API_TOKEN = os.environ.get('SIGNALWIRE_API_TOKEN')
    SIGNALWIRE_SPACE_URL = os.environ.get('SIGNALWIRE_SPACE_URL')
    
    # LLM configuration
    LLM_SERVER_URL = os.environ.get('LLM_SERVER_URL', 'http://10.0.0.4:11434')
    LLM_MODEL = os.environ.get('LLM_MODEL', 'dolphin-mistral:7b-v2.8')
    LLM_TIMEOUT = int(os.environ.get('LLM_TIMEOUT', 30))
    LLM_MAX_TOKENS = int(os.environ.get('LLM_MAX_TOKENS', 150))
    LLM_TEMPERATURE = float(os.environ.get('LLM_TEMPERATURE', 0.7))
    LLM_RETRY_ATTEMPTS = int(os.environ.get('LLM_RETRY_ATTEMPTS', 2))
    
    # Redis configuration
    REDIS_URL = os.environ.get('REDIS_URL', 'redis://:AssisText2025!Redis@localhost:6379/0')
    CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://:AssisText2025!Redis@localhost:6379/0')
    CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', 'redis://:AssisText2025!Redis@localhost:6379/0')
    
    # Application settings
    BASE_URL = os.environ.get('BASE_URL', 'https://backend.assitext.ca')
    VALIDATE_SIGNALWIRE_SIGNATURE = os.environ.get('VALIDATE_SIGNALWIRE_SIGNATURE', 'False').lower() == 'true'
    
    # Rate limiting
    RATELIMIT_STORAGE_URL = os.environ.get('RATELIMIT_STORAGE_URL', 'redis://:AssisText2025!Redis@localhost:6379/1')
    MAX_DAILY_AI_RESPONSES = int(os.environ.get('MAX_DAILY_AI_RESPONSES', 100))
    MAX_MESSAGES_PER_5MIN = int(os.environ.get('MAX_MESSAGES_PER_5MIN', 3))

class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = encode_database_url(
        os.environ.get('DEV_DATABASE_URL') or 
        'postgresql://app_user:AssisText2025!SecureDB@localhost:5432/assistext_dev'
    )

class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = encode_database_url(
        os.environ.get('DATABASE_URL') or 
        'postgresql://app_user:AssisText2025!SecureDB@localhost:5432/assistext_prod'
    )

class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = encode_database_url(
        os.environ.get('TEST_DATABASE_URL') or 
        'postgresql://app_user:AssisText2025!SecureDB@localhost:5432/assistext_test'
    )

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': ProductionConfig
}
