# =============================================================================
# app/extensions.py
"""
FLASK EXTENSIONS - CORRECTED VERSION
Centralized extension initialization for PostgreSQL environment
"""
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager

from flask_mail import Mail
import redis

# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()
mail = Mail()

# Rate limiter with Redis backend


# Redis client for caching and sessions
redis_client = None

def init_redis(app):
    """Initialize Redis client"""
    global redis_client
    try:
        redis_url = app.config.get('REDIS_URL', 'redis://localhost:6379')
        redis_client = redis.from_url(redis_url, decode_responses=True)
        redis_client.ping()  # Test connection
        app.logger.info("✅ Redis connection established")
        return redis_client
    except Exception as e:
        app.logger.error(f"❌ Redis connection failed: {e}")
        return None

def get_redis():
    """Get Redis client instance"""
    return redis_client
