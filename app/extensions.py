# app/extensions.py - Fixed Flask Extensions
"""
Flask Extensions - Centralized extension initialization
"""
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_mail import Mail
import redis

# Initialize extensions without app context
db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()
mail = Mail()

# Rate limiter with Redis backend
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour", "10 per minute"]
)

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