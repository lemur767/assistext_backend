import os
import logging
from app import create_app
from app.extensions import socketio

# Create application
app = create_app(os.environ.get('FLASK_ENV', 'production'))

# Configure logging for production
if not app.debug:
    # Create logs directory if it doesn't exist
    if not os.path.exists('logs'):
        os.mkdir('logs')
    
    # Set up file logging
    file_handler = logging.FileHandler('logs/sms_ai_responder.log')
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    
    app.logger.setLevel(logging.INFO)
    app.logger.info('SMS AI Responder startup (production)')

if __name__ == "__main__":
    # For development with SocketIO
    socketio.run(app, debug=app.config.get('DEBUG', False), host='https://assitext.ca', port=5000)

