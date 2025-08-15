# =============================================================================
# app/extensions.py
"""
FLASK EXTENSIONS - CORRECTED VERSION
Centralized extension initialization for PostgreSQL environment
"""
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()
limiter = Limiter(key_func=get_remote_address)
