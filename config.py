import os
from datetime import timedelta

class Config:
    """Base configuration"""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'eGJheGYyeGZmbHgxNng5NXhjYXhiM3hkZnhlNnhiOHhiOXg5N3g4ZXhmNUJwU3gxMw==')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # JWT Configuration
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'xbaxf2xfflx16x95xcaxb3xdfxe6xb5!x1excaxd6x15Cxd7x97x08xb9x97x8exf5BpSx13')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=24)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    
    # SignalWire Configuration
    SIGNALWIRE_SPACE_URL = os.environ.get('SIGNALWIRE_SPACE_URL')
    SIGNALWIRE_PROJECT_ID = os.environ.get('SIGNALWIRE_PROJECT_ID')
    SIGNALWIRE_AUTH_TOKEN = os.environ.get('SIGNALWIRE_AUTH_TOKEN')
    
    # Application
    BASE_URL = os.environ.get('BASE_URL', 'http://localhost:5000')

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = 'postgresql://app_user:Assistext2025Secure@localhost/assistext_prod'
    REDIS_URL = 'redis://localhost:6379/0'
    
class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = 'postgresql://app_user:Assistext2025Secure@localhost/assistext_prod'
    REDIS_URL = 'redis://:Assistext2025Secure@localhost:6379/0'
    
    # Email Configuration
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'localhost')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@assistext.ca')
