# app/extensions.py - Clean extensions initialization
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from flask_socketio import SocketIO

# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()
socketio = SocketIO()

# Optional Celery (if you're using it)
try:
    from celery import Celery
    celery = Celery(__name__)
except ImportError:
    celery = None