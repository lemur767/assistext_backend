
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from flask_socketio import SocketIO
from celery import Celery

# Initialize extensions without configuration
# These will be configured in the create_app function
db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()
socketio = SocketIO()

# Celery will be configured later in create_app
celery = Celery(__name__)

# Remove task_queue initialization from here
# It should be handled in the app factory function