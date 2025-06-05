# wsgi.py - CORRECTED for production deployment
import os
import logging
from app import create_app
from app.extensions import socketio

# Create application
app = create_app(os.environ.get('FLASK_ENV', 'development'))

# Configure logging for production
if not app.debug:
    # Create logs directory if it doesn't exist
    if not os.path.exists('logs'):
        os.mkdir('logs')
    
    # Set up file logging with rotation
    from logging.handlers import RotatingFileHandler
    
    file_handler = RotatingFileHandler(
        'logs/sms_ai_responder.log', 
        maxBytes=10240000,  # 10MB
        backupCount=10
    )
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    
    app.logger.setLevel(logging.INFO)
    app.logger.info('SMS AI Responder startup (production)')

# For Gunicorn (production) - this won't be called
# For development only
if __name__ == "__main__":
    # FIXED: Use proper host binding, not a URL
    socketio.run(
        app, 
        debug=app.config.get('DEBUG', False), 
        host='0.0.0.0',  # FIXED: was 'https://assitext.ca' 
        port=5000
    )