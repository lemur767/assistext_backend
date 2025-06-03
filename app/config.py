import os
from datetime import timedelta
from dotenv import load_dotenv

from cryptography.fernet import Fernet

load_dotenv()

def generate_encryption_key():
    return Fernet.generate_key().decode()
class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY')
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    #DB setup
    DB_NAME = os.environ.get('DB_NAME')
    DB_USER = os.environ.get('DB_USER')
    DB_PASS = os.environ.get('DB_PASS')
   
    
    # Twilio configuration
    
    #Master Accounts
    TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID')
    TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN')
    
    VERIFY_TWILIO_SIGNATURE = os.environ.get('VERIFY_TWILIO_SIGNATURE', 'True') == 'True'
    
    TWILIO_DEFAULT_TO_SUBACCOUNT = os.environ.get('TWILIO_DEFAULT_TO_SUBACCOUNT', 'True') == 'True'
    
    TWILIO_SET_TRIAL_LIMITS = os.environ.get('TWILIO_SET_TRIAL_LIMITS', 'True') == 'True'
    
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', 'http://assitext.ca','https://assitext.ca').split(',')
    
    BASE_URL = os.environ.get('BASE_URL', 'https://assitext.ca/')
    
    SMS_RATE = float(os.environ.get('SMS_RATE', '0.0075'))  # Cost per SMS
    VOICE_RATE = float(os.environ.get('VOICE_RATE', '0.015'))  # Cost per minute
    NUMBER_RATE = float(os.environ.get('NUMBER_RATE', '1.0'))  # Cost per number per month
    MARKUP_PERCENTAGE = float(os.environ.get('MARKUP_PERCENTAGE', '20.0'))  # Markup percentage
    #Local LLM
    LLM_BASE_URL = os.environ.get('LLM_BASE_URL', 'http://10.0.0.6:11434/api')
    LLM_MODEL = os.environ.get('LLM_MODEL', 'dolphin3')
    LLM_TIMEOUT = int(os.environ.get('LLM_TIMEOUT', '30'))
    LLM_MAX_TOKENS = int(os.environ.get('LLM_MAX_TOKENS', '150'))
    LLM_TEMPERATURE = float(os.environ.get('LLM_TEMPERATURE', '0.7'))
    
    # Message Processing
    MAX_MESSAGE_LENGTH = int(os.environ.get('MAX_MESSAGE_LENGTH', '1600'))
    AUTO_REPLY_ENABLED = os.environ.get('AUTO_REPLY_ENABLED', 'True').lower() == 'true'
    
    # Webhook Configuration
    WEBHOOK_TIMEOUT = int(os.environ.get('WEBHOOK_TIMEOUT', '5'))  # Seconds to respond to Twilio
      
    # Stripe configuration
    STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY')
    STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET')
    
    # Celery configuration
    CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL')
    CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND')
    
    ENCRYPTION_KEY = os.environ.get('ENCRYPTION_KEY') or generate_encryption_key()
class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL_DEV') or \
        f'postgresql://{Config.DB_USER}:{Config.DB_PASS}@localhost:5432/{Config.DB_NAME}'
        
       # Development-specific CORS (more permissive)
    CORS_ORIGINS = [
        'http://localhost:3000',  # React dev server
        'http://localhost:5173',  # Vite dev server
        'http://127.0.0.1:3000',
        'http://127.0.0.1:5173'
    ]

class ProductionConfig(Config):
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        f'postgresql://{Config.DB_USER}:{Config.DB_PASS}@localhost:5432/{Config.DB_NAME}'
    VERIFY_TWILIO_SIGNATURE = True
    
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', '').split(',') if os.environ.get('CORS_ORIGINS') else []
    
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}